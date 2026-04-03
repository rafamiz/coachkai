"""One-time script to merge duplicate users with different phone formats."""
import db

def main():
    db.init_db()
    conn = db.get_conn()
    c = db._cur(conn)

    # Get all users with a phone number
    c.execute(db._q("SELECT id, telegram_id, phone, onboarding_complete FROM users WHERE phone IS NOT NULL AND phone != ''"))
    rows = [dict(r) for r in c.fetchall()]

    # Group by normalized phone
    groups = {}
    for row in rows:
        norm = db.normalize_phone(row["phone"])
        if not norm:
            continue
        groups.setdefault(norm, []).append(row)

    deleted = 0
    updated_phones = 0
    for norm_phone, users in groups.items():
        # Update all phone fields to normalized form
        for u in users:
            if u["phone"] != norm_phone:
                c.execute(db._q("UPDATE users SET phone = ? WHERE id = ?"), (norm_phone, u["id"]))
                updated_phones += 1
                print(f"  Normalized phone: '{u['phone']}' -> '{norm_phone}' (user id={u['id']})")

        if len(users) <= 1:
            continue

        print(f"\nDuplicate group for phone {norm_phone}: {len(users)} records")

        # Pick keeper: prefer onboarding_complete=1, then highest id
        users.sort(key=lambda u: (u.get("onboarding_complete") or 0, u["id"]), reverse=True)
        keeper = users[0]
        dupes = users[1:]

        print(f"  Keeping user id={keeper['id']} (tid={keeper['telegram_id']}, onboarding={keeper.get('onboarding_complete')})")
        for d in dupes:
            print(f"  Deleting user id={d['id']} (tid={d['telegram_id']}, onboarding={d.get('onboarding_complete')})")
            c.execute(db._q("DELETE FROM users WHERE id = ?"), (d["id"],))
            deleted += 1

    conn.commit()
    db._release(conn)
    print(f"\nDone. Deleted {deleted} duplicate(s), normalized {updated_phones} phone(s).")


if __name__ == "__main__":
    main()
