// Supabase Edge Function: Affiliate payout processor (Stripe Connect transfers)
//
// Purpose:
// - After the 1-day refund window, automatically transfer affiliate commissions to the affiliate's
//   connected Stripe account (Stripe Connect).
//
// Safety:
// - Designed to be run on a schedule (cron) or manually.
// - Idempotent-ish: we only pay rows with stripe_transfer_id IS NULL.
// - Uses Stripe idempotency keys per commission id.
//
// Required secrets (Supabase Dashboard → Edge Functions → Secrets):
// - SB_URL
// - SB_SERVICE_ROLE_KEY
// - STRIPE_SECRET_KEY (test or live, must match the environment you want to pay out from)
//
// Required tables:
// - public.affiliate_commissions (with available_at, commission_cents, currency, stripe_transfer_id)
// - public.affiliate_payout_accounts (affiliate_user_id -> stripe_account_id, status='active')
//
// NOTE:
// - This does NOT run from the Streamlit app by default. Keep it separate and controlled.

import Stripe from "https://esm.sh/stripe@14.25.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

function requireEnv(name: string): string {
  const v = Deno.env.get(name);
  if (!v) throw new Error(`Missing env var: ${name}`);
  return v;
}

function json(res: unknown, status = 200) {
  return new Response(JSON.stringify(res), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const supabaseUrl = requireEnv("SB_URL");
const supabaseServiceKey = requireEnv("SB_SERVICE_ROLE_KEY");
const stripeSecretKey = requireEnv("STRIPE_SECRET_KEY");

const stripe = new Stripe(stripeSecretKey, { apiVersion: "2023-10-16" });

const sb = createClient(supabaseUrl, supabaseServiceKey, {
  auth: { persistSession: false },
});

type CommissionRow = {
  id: string;
  affiliate_user_id: string;
  referred_user_id: string;
  stripe_invoice_id: string | null;
  amount_cents: number;
  commission_cents: number;
  currency: string;
  available_at: string;
  stripe_transfer_id: string | null;
  status: string;
};

type PayoutAccountRow = {
  affiliate_user_id: string;
  stripe_account_id: string;
  status: string;
};

async function getActivePayoutAccount(affiliateUserId: string): Promise<PayoutAccountRow | null> {
  const { data, error } = await sb
    .from("affiliate_payout_accounts")
    .select("affiliate_user_id,stripe_account_id,status")
    .eq("affiliate_user_id", affiliateUserId)
    .maybeSingle();
  if (error || !data) return null;
  const status = (data.status ?? "").toString().toLowerCase();
  // Treat "pending" as usable (common during initial onboarding). Only block explicit pauses.
  if (status === "paused") return null;
  if (!data.stripe_account_id) return null;
  return data as PayoutAccountRow;
}

async function markPaid(id: string, transferId: string) {
  await sb
    .from("affiliate_commissions")
    .update({
      status: "paid",
      stripe_transfer_id: transferId,
      paid_at: new Date().toISOString(),
    })
    .eq("id", id);
}

async function markPayable(id: string) {
  await sb
    .from("affiliate_commissions")
    .update({ status: "payable" })
    .eq("id", id)
    .eq("status", "pending");
}

async function markFailed(id: string) {
  // Minimal + schema-safe: we only flip status so this row won't be retried forever.
  // (We don't assume an error_message column exists.)
  await sb.from("affiliate_commissions").update({ status: "failed" }).eq("id", id);
}

function isPermanentStripeError(errStr: string): boolean {
  const s = (errStr || "").toLowerCase();
  return (
    s.includes("idempotent requests can only be used") ||
    s.includes("stripe_balance.stripe_transfers") ||
    s.includes("funds can't be sent to accounts located in") ||
    s.includes("restricted outside of your platform's region")
  );
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ ok: false, error: "Method not allowed" }, 405);

  // Optional guard: require a shared secret header, if configured.
  const guard = Deno.env.get("AFFILIATE_PAYOUTS_SECRET") ?? "";
  if (guard) {
    const got = req.headers.get("x-tradylo-admin") ?? "";
    if (got !== guard) return json({ ok: false, error: "Unauthorized" }, 401);
  }

  const nowIso = new Date().toISOString();

  // Fetch a small batch of commissions that are past the refund window and not yet transferred.
  const { data, error } = await sb
    .from("affiliate_commissions")
    .select(
      "id,affiliate_user_id,referred_user_id,stripe_invoice_id,amount_cents,commission_cents,currency,available_at,stripe_transfer_id,status",
    )
    .is("stripe_transfer_id", null)
    .in("status", ["pending", "payable"])
    .lte("available_at", nowIso)
    .order("available_at", { ascending: true })
    .limit(50);

  if (error) return json({ ok: false, error: String(error.message ?? error) }, 500);

  const rows = (data ?? []) as CommissionRow[];
  let processed = 0;
  let paid = 0;
  const skipped: Array<Record<string, string>> = [];

  for (const row of rows) {
    processed += 1;

    // Ensure status is at least "payable" once window passes.
    if (row.status === "pending") {
      await markPayable(row.id);
    }

    const acct = await getActivePayoutAccount(row.affiliate_user_id);
    if (!acct) {
      skipped.push({ id: row.id, reason: "missing_or_inactive_payout_account" });
      continue;
    }

    const destination = acct.stripe_account_id;

    const amount = Number(row.commission_cents ?? 0);
    if (!Number.isFinite(amount) || amount <= 0) {
      skipped.push({ id: row.id, reason: "invalid_commission_amount", destination });
      continue;
    }

    const currency = (row.currency || "usd").toString().toLowerCase();

    try {
      const transfer = await stripe.transfers.create(
        {
          amount,
          currency,
          destination,
          metadata: {
            affiliate_user_id: row.affiliate_user_id,
            referred_user_id: row.referred_user_id,
            stripe_invoice_id: row.stripe_invoice_id ?? "",
            commission_id: row.id,
          },
        },
        { idempotencyKey: `tradylo_comm_${row.id}` },
      );
      const transferId = (transfer.id || "").toString();
      if (transferId) {
        await markPaid(row.id, transferId);
        paid += 1;
      } else {
        skipped.push({ id: row.id, reason: "transfer_missing_id", destination });
      }
    } catch (err) {
      const errStr = String(err);
      const reason = `stripe_error:${errStr}`.slice(0, 180);
      skipped.push({ id: row.id, reason, destination });
      if (isPermanentStripeError(errStr)) {
        await markFailed(row.id);
      }
    }
  }

  return json({ ok: true, processed, paid, skipped });
});
