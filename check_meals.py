import db; db.init_db()
TID = 99991
meals = db.get_today_meals(TID)
for m in meals:
    print(f"  {m['description'][:40]} | {m['meal_type']} | {m['calories_est']} kcal | p:{m.get('proteins_g',0):.0f}g c:{m.get('carbs_g',0):.0f}g f:{m.get('fats_g',0):.0f}g")
print(f"  TOTAL: {sum(m.get('calories_est',0) or 0 for m in meals)} kcal")
