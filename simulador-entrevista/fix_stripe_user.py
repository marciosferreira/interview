"""
Run once on the server to populate stripe info for a hunter user.
Usage:  python fix_stripe_user.py <user_email> [customer_id]
"""
import os, sys, sqlite3, stripe
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

def find_db():
    for c in ["sessions.db", "interview_simulator.db"]:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("DB not found")

def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_stripe_user.py <email> [customer_id]")
        sys.exit(1)

    email = sys.argv[1]
    force_customer_id = sys.argv[2] if len(sys.argv) > 2 else None

    db_path = find_db()
    print(f"Using DB: {db_path}")
    conn = sqlite3.connect(db_path)

    user = conn.execute(
        "SELECT id, email, plan, stripe_customer_id, stripe_subscription_id FROM users WHERE email = ?",
        (email.lower(),)
    ).fetchone()
    if not user:
        print(f"User not found: {email}")
        return

    user_id, user_email, plan, cur_cid, cur_sid = user
    print(f"User: {user_id} | plan={plan} | customer={cur_cid} | sub={cur_sid}")

    if force_customer_id:
        customer_id = force_customer_id
    else:
        customers = list(stripe.Customer.list(email=email, limit=10).auto_paging_iter())
        if not customers:
            print("No Stripe customer found.")
            return
        # Pick the one with an active subscription
        customer_id = None
        sub_id = None
        period_end = None
        for cus in customers:
            subs = list(stripe.Subscription.list(customer=cus.id, status="all", limit=5).auto_paging_iter())
            active = [s for s in subs if s.status in ("active", "trialing", "past_due")]
            if active:
                customer_id = cus.id
                sub_id = active[0].id
                period_end = active[0].current_period_end if active[0].cancel_at_period_end else None
                print(f"Found active sub {sub_id} for customer {customer_id}")
                break
        if not customer_id:
            # Fallback: pick most recent customer with any sub
            cus = customers[0]
            customer_id = cus.id
            subs = list(stripe.Subscription.list(customer=cus.id, status="all", limit=5).auto_paging_iter())
            sub_id = subs[0].id if subs else ""
            period_end = None
            print(f"Fallback: customer {customer_id} sub {sub_id}")

    conn.execute(
        "UPDATE users SET stripe_customer_id = ?, stripe_subscription_id = ?, stripe_cancel_at = ? WHERE id = ?",
        (customer_id, sub_id or "", period_end, user_id),
    )
    conn.commit()

    row = conn.execute(
        "SELECT stripe_customer_id, stripe_subscription_id, stripe_cancel_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    print(f"Saved: customer={row[0]} | sub={row[1]} | cancel_at={row[2]}")
    conn.close()

if __name__ == "__main__":
    main()
