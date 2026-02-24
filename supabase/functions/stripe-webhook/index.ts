// Supabase Edge Function: Stripe webhook handler
// - Verifies Stripe signature
// - Stores events in `public.stripe_events`
// - Updates `public.entitlements` for Pro access
// - Records recurring affiliate commissions in `public.affiliate_commissions`
//
// This function is safe to deploy even while PAYWALL_ENABLED/STRIPE_ENABLED are false in Streamlit:
// it only writes backend rows when Stripe sends events.

import Stripe from "https://esm.sh/stripe@14.25.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

type EntitlementPlan = "free" | "pro" | "grandfathered" | "lifetime";

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

// NOTE: Supabase Edge Function secrets cannot start with the `SUPABASE_` prefix.
// Use SB_URL + SB_SERVICE_ROLE_KEY in Supabase Dashboard → Edge Functions → Secrets.
const supabaseUrl = requireEnv("SB_URL");
const supabaseServiceKey = requireEnv("SB_SERVICE_ROLE_KEY");
const stripeSecretKey = requireEnv("STRIPE_SECRET_KEY");
const stripeWebhookSecret = requireEnv("STRIPE_WEBHOOK_SECRET");

const stripe = new Stripe(stripeSecretKey, { apiVersion: "2023-10-16" });

const sb = createClient(supabaseUrl, supabaseServiceKey, {
  auth: { persistSession: false },
});

type BillingConfig = {
  affiliate_promo_start_at: string | null;
  affiliate_promo_end_at: string | null;
  promo_commission_percent: number | null;
  default_commission_percent: number | null;
};

async function getBillingConfig(): Promise<BillingConfig | null> {
  try {
    const { data, error } = await sb
      .from("billing_config")
      .select(
        "affiliate_promo_start_at,affiliate_promo_end_at,promo_commission_percent,default_commission_percent",
      )
      .eq("id", 1)
      .maybeSingle();
    if (error || !data) return null;
    return {
      affiliate_promo_start_at: (data.affiliate_promo_start_at as string) ?? null,
      affiliate_promo_end_at: (data.affiliate_promo_end_at as string) ?? null,
      promo_commission_percent: Number(data.promo_commission_percent ?? null),
      default_commission_percent: Number(data.default_commission_percent ?? null),
    };
  } catch (_) {
    return null;
  }
}

function percentForAffiliateCommission(params: {
  basePercent: number;
  invoiceCreatedUnixSeconds: number | null;
  cfg: BillingConfig | null;
}): number {
  let pct = params.basePercent;

  const cfg = params.cfg;
  const created = params.invoiceCreatedUnixSeconds;
  if (!cfg || !Number.isFinite(created as number)) return pct;

  const startMs = cfg.affiliate_promo_start_at ? Date.parse(cfg.affiliate_promo_start_at) : NaN;
  const endMs = cfg.affiliate_promo_end_at ? Date.parse(cfg.affiliate_promo_end_at) : NaN;
  const createdMs = Number(created) * 1000;

  const promoPct = Number(cfg.promo_commission_percent ?? NaN);
  const defaultPct = Number(cfg.default_commission_percent ?? NaN);

  // If configured, never go below the default.
  if (Number.isFinite(defaultPct) && defaultPct > pct) pct = defaultPct;

  // If we're inside the promo window, bump up (but don't override higher custom rates).
  if (Number.isFinite(startMs) && Number.isFinite(endMs) && createdMs >= startMs && createdMs < endMs) {
    if (Number.isFinite(promoPct) && promoPct > pct) pct = promoPct;
  }

  return pct;
}

async function insertStripeEvent(eventId: string, eventType: string, payload: unknown) {
  // Best-effort: never fail the webhook solely because logging failed.
  try {
    await sb.from("stripe_events").insert({
      event_id: eventId,
      event_type: eventType,
      payload,
    });
  } catch (_) {
    // ignore
  }
}

async function getEntitlementPlan(userId: string): Promise<EntitlementPlan | null> {
  const { data, error } = await sb
    .from("entitlements")
    .select("plan")
    .eq("user_id", userId)
    .maybeSingle();
  if (error) return null;
  const plan = (data?.plan ?? "") as string;
  if (!plan) return null;
  return plan.toLowerCase() as EntitlementPlan;
}

async function setProEntitlement(params: {
  userId: string;
  stripeCustomerId?: string | null;
  stripeSubscriptionId?: string | null;
  subscriptionStatus?: string | null;
  currentPeriodEnd?: string | null;
}) {
  const row: Record<string, unknown> = {
    user_id: params.userId,
    plan: "pro",
    trade_limit: null,
    stripe_customer_id: params.stripeCustomerId ?? null,
    stripe_subscription_id: params.stripeSubscriptionId ?? null,
    subscription_status: params.subscriptionStatus ?? null,
    current_period_end: params.currentPeriodEnd ?? null,
  };
  await sb.from("entitlements").upsert(row, { onConflict: "user_id" });
}

async function downgradeToFreeIfNotGrandfathered(userId: string, status: string) {
  const plan = await getEntitlementPlan(userId);
  if (plan === "grandfathered" || plan === "lifetime") return;

  await sb.from("entitlements").upsert(
    {
      user_id: userId,
      plan: "free",
      trade_limit: 15,
      subscription_status: status,
    },
    { onConflict: "user_id" },
  );
}

async function userIdForSubscription(stripeSubscriptionId: string): Promise<string | null> {
  const { data, error } = await sb
    .from("entitlements")
    .select("user_id")
    .eq("stripe_subscription_id", stripeSubscriptionId)
    .maybeSingle();
  if (error) return null;
  return (data?.user_id as string) || null;
}

async function recordAffiliateCommissionForInvoice(params: {
  referredUserId: string;
  stripeInvoiceId: string;
  amountPaidCents: number;
  currency: string;
  stripeCustomerId?: string | null;
  invoiceCreatedUnixSeconds?: number | null;
  billingConfig?: BillingConfig | null;
}) {
  if (!params.referredUserId || !params.stripeInvoiceId) return;
  if (!Number.isFinite(params.amountPaidCents) || params.amountPaidCents <= 0) return;

  try {
    // Was this user referred?
    const { data: refRow } = await sb
      .from("referrals")
      .select("affiliate_user_id,code")
      .eq("referred_user_id", params.referredUserId)
      .maybeSingle();
    if (!refRow) return;

    const affiliateUserId = (refRow.affiliate_user_id as string) || "";
    const code = (refRow.code as string) || "";
    if (!affiliateUserId || !code) return;

    // Is the code still active and what %?
    const { data: codeRow } = await sb
      .from("affiliate_codes")
      .select("commission_percent,is_active")
      .eq("code", code)
      .maybeSingle();
    if (!codeRow || codeRow.is_active === false) return;

    const basePct = Number(codeRow.commission_percent ?? 0);
    const pct = percentForAffiliateCommission({
      basePercent: basePct,
      invoiceCreatedUnixSeconds: params.invoiceCreatedUnixSeconds ?? null,
      cfg: params.billingConfig ?? null,
    });
    if (!Number.isFinite(pct) || pct <= 0) return;

    const commissionCents = Math.round((params.amountPaidCents * pct) / 100);
    if (commissionCents <= 0) return;

    // Hold commissions for 1 day (refund window).
    const availableAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

    // Requires a unique constraint on (affiliate_user_id, stripe_invoice_id) to be truly idempotent.
    await sb.from("affiliate_commissions").upsert(
      {
        affiliate_user_id: affiliateUserId,
        referred_user_id: params.referredUserId,
        stripe_invoice_id: params.stripeInvoiceId,
        stripe_customer_id: params.stripeCustomerId ?? null,
        amount_cents: params.amountPaidCents,
        commission_cents: commissionCents,
        currency: params.currency,
        status: "pending",
        available_at: availableAt,
      },
      { onConflict: "affiliate_user_id,stripe_invoice_id" },
    );
  } catch (_) {
    // Best-effort: affiliate tracking should never block billing updates.
    return;
  }
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ ok: false, error: "Method not allowed" }, 405);

  const sig = req.headers.get("stripe-signature") ?? "";
  const rawBody = await req.text();

  let event: Stripe.Event;
  let parsedPayload: unknown = null;
  try {
    parsedPayload = JSON.parse(rawBody);
  } catch (_) {
    parsedPayload = { raw: rawBody };
  }

  try {
    event = await stripe.webhooks.constructEventAsync(rawBody, sig, stripeWebhookSecret);
  } catch (err) {
    await insertStripeEvent("invalid", "invalid_signature", parsedPayload);
    return json({ ok: false, error: "Invalid signature" }, 400);
  }

  await insertStripeEvent(event.id, event.type, parsedPayload);

  try {
    if (event.type === "checkout.session.completed") {
      const session = event.data.object as Stripe.Checkout.Session;
      const userId = (session.client_reference_id || session.metadata?.user_id || "").toString();
      if (!userId) return json({ ok: true });

      const customerId = (session.customer || "").toString() || null;
      const subscriptionId = (session.subscription || "").toString() || null;

      let currentPeriodEnd: string | null = null;
      let subscriptionStatus: string | null = null;
      if (subscriptionId) {
        try {
          const sub = await stripe.subscriptions.retrieve(subscriptionId);
          subscriptionStatus = (sub.status || "").toString() || null;
          currentPeriodEnd = sub.current_period_end
            ? new Date(sub.current_period_end * 1000).toISOString()
            : null;
        } catch (_) {
          // ignore
        }
      }

      await setProEntitlement({
        userId,
        stripeCustomerId: customerId,
        stripeSubscriptionId: subscriptionId,
        subscriptionStatus,
        currentPeriodEnd,
      });
    }

    if (event.type === "invoice.payment_succeeded") {
      const invoice = event.data.object as Stripe.Invoice;
      const subscriptionId = (invoice.subscription || "").toString();
      const customerId = (invoice.customer || "").toString() || null;
      const invoiceId = (invoice.id || "").toString();
      const amountPaid = Number(invoice.amount_paid ?? 0);
      const currency = (invoice.currency || "usd").toString();
      const invoiceCreated = Number((invoice as any).created ?? null);

      if (!subscriptionId) return json({ ok: true });
      const userId = await userIdForSubscription(subscriptionId);
      if (!userId) return json({ ok: true });

      let currentPeriodEnd: string | null = null;
      let subscriptionStatus: string | null = null;
      try {
        const sub = await stripe.subscriptions.retrieve(subscriptionId);
        subscriptionStatus = (sub.status || "").toString() || null;
        currentPeriodEnd = sub.current_period_end
          ? new Date(sub.current_period_end * 1000).toISOString()
          : null;
      } catch (_) {
        // ignore
      }

      await setProEntitlement({
        userId,
        stripeCustomerId: customerId,
        stripeSubscriptionId: subscriptionId,
        subscriptionStatus,
        currentPeriodEnd,
      });

      if (invoiceId && amountPaid > 0) {
        const billingConfig = await getBillingConfig();
        await recordAffiliateCommissionForInvoice({
          referredUserId: userId,
          stripeInvoiceId: invoiceId,
          amountPaidCents: amountPaid,
          currency,
          stripeCustomerId: customerId,
          invoiceCreatedUnixSeconds: Number.isFinite(invoiceCreated) ? invoiceCreated : null,
          billingConfig,
        });
      }
    }

    if (event.type === "customer.subscription.deleted") {
      const sub = event.data.object as Stripe.Subscription;
      const subscriptionId = (sub.id || "").toString();
      if (!subscriptionId) return json({ ok: true });
      const userId = await userIdForSubscription(subscriptionId);
      if (!userId) return json({ ok: true });
      await downgradeToFreeIfNotGrandfathered(userId, "canceled");
    }

    if (event.type === "customer.subscription.updated") {
      const sub = event.data.object as Stripe.Subscription;
      const subscriptionId = (sub.id || "").toString();
      if (!subscriptionId) return json({ ok: true });
      const userId = await userIdForSubscription(subscriptionId);
      if (!userId) return json({ ok: true });

      const status = (sub.status || "").toString();
      if (status === "active" || status === "trialing") {
        await setProEntitlement({
          userId,
          stripeCustomerId: (sub.customer || "").toString() || null,
          stripeSubscriptionId: subscriptionId,
          subscriptionStatus: status,
          currentPeriodEnd: sub.current_period_end
            ? new Date(sub.current_period_end * 1000).toISOString()
            : null,
        });
      } else if (status === "canceled" || status === "unpaid" || status === "past_due") {
        await downgradeToFreeIfNotGrandfathered(userId, status);
      }
    }
  } catch (err) {
    // Return 200 so Stripe won't keep retrying due to our internal issue;
    // events are still logged in `stripe_events` for debugging.
    return json({ ok: true, warning: "handler_error", detail: String(err) });
  }

  return json({ ok: true });
});
