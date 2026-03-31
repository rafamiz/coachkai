import { NextRequest, NextResponse } from 'next/server';
import { getDueReminders, markReminderSent, getWhatsAppProvider } from '@nutricoach/core';

export async function GET(req: NextRequest) {
  // Verify cron secret
  const authHeader = req.headers.get('authorization');
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const reminders = await getDueReminders();
  const provider = getWhatsAppProvider();

  const messages: Record<string, string> = {
    meal: "🍽️ ¡{{name}}, hora de comer! Mandame una foto de tu {{label}} y te digo los macros al toque 💪",
    water: "💧 ¡{{name}}! ¿Ya tomaste agua? Acordate de hidratarte. Decime cuántos vasos llevás hoy",
    weigh_in: "⚖️ ¡{{name}}, hora de pesarte! Mandame tu peso de hoy así lo registro",
    custom: "🔔 {{name}}: {{label}}",
  };

  let sent = 0;
  for (const reminder of reminders) {
    const today = new Date().toISOString().split('T')[0];
    if (reminder.last_sent?.startsWith(today)) continue; // Already sent today

    const template = messages[reminder.type] || messages.custom;
    const text = template
      .replace('{{name}}', reminder.first_name || 'there')
      .replace('{{label}}', reminder.label || 'your reminder');

    try {
      await provider.sendText(reminder.phone, text);
      await markReminderSent(reminder.id);
      sent++;
    } catch (err) {
      console.error(`Failed to send reminder ${reminder.id}:`, err);
    }
  }

  return NextResponse.json({ sent, total: reminders.length });
}
