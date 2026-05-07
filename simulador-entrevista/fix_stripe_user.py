"""
Run once on the server to populate stripe_customer_id and stripe_subscription_id
for a user whose plan is already 'hunter' but Stripe info wasn't stored.

Usage:  python fix_stripe_user.py <user_email>
"""
import os, sys, sqlite3, stripe
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

def find_db():
    candidates = ["sessions.db", "interview_simulator.db"]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("DB not found")

def main():
    email = sys.argv[1] if len(sys.argv) > 1 else input("User email: ").strip()

    db_path = find_db()
    conn = sqlite3.connect(db_path)

    user = conn.execute("SELECT id, email, plan FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if not user:
        print(f"User not found: {email}")
        return
    user_id, user_email, plan = user
    print(f"User: {user_id} | {user_email} | plan={plan}")

    customers = list(stripe.Customer.list(email=email, limit=10).auto_paging_iter())
    if not customers:
        print("No Stripe customer found for this email.")
        return

    print(f"\nFound {len(customers)} Stripe customer(s):")
    for i, c in enumerate(customers):
        subs = list(stripe.Subscription.list(customer=c.id, limit=5, status="all").auto_paging_iter())
        active = [s for s in subs if s.status in ("active", "trialing")]
        print(f"  [{i}] {c.id} — {len(subs)} subscriptions, {len(active)} active")
        for s in subs:
            print(f"       sub {s.id} status={s.status} cancel_at_period_end={s.cancel_at_period_end}")

    idx = int(input("\nPick customer index to use [0]: ") or "0")
    cus = customers[idx]

    subs = list(stripe.Subscription.list(customer=cus.id, limit=5, status="all").auto_paging_iter())
    active_subs = [s for s in subs if s.status in ("active", "trialing", "past_due")]
    sub = active_subs[0] if active_subs else (subs[0] if subs else None)

    customer_id     = cus.id
    subscription_id = sub.id if sub else ""
    cancel_at       = sub.current_period_end if (sub and sub.cancel_at_period_end) else None

    print(f"\nWill write:")
    print(f"  stripe_customer_id     = {customer_id}")
    print(f"  stripe_subscription_id = {subscription_id}")
    print(f"  stripe_cancel_at       = {cancel_at}")

    confirm = input("Confirm? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    conn.execute(
        "UPDATE users SET stripe_customer_id = ?, stripe_subscription_id = ?, stripe_cancel_at = ? WHERE id = ?",
        (customer_id, subscription_id, cancel_at, user_id),
    )
    conn.commit()
    conn.close()
    print("Done. Reload the profile page.")

if __name__ == "__main__":
    main()
