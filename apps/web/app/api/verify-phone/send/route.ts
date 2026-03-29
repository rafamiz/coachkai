import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  const { phone } = await req.json();

  if (!phone) {
    return NextResponse.json({ error: 'Phone required' }, { status: 400 });
  }

  // Use Twilio Verify for OTP
  const accountSid = process.env.TWILIO_ACCOUNT_SID;
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  const verifyServiceSid = process.env.TWILIO_VERIFY_SERVICE_SID;

  if (!verifyServiceSid) {
    // Fallback: skip verification in dev
    return NextResponse.json({ status: 'sent', dev: true });
  }

  const response = await fetch(
    `https://verify.twilio.com/v2/Services/${verifyServiceSid}/Verifications`,
    {
      method: 'POST',
      headers: {
        Authorization: 'Basic ' + Buffer.from(`${accountSid}:${authToken}`).toString('base64'),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({ To: phone, Channel: 'sms' }),
    },
  );

  if (!response.ok) {
    const err = await response.json();
    return NextResponse.json({ error: 'Failed to send OTP', detail: err }, { status: 500 });
  }

  return NextResponse.json({ status: 'sent' });
}
