import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  const { phone, code } = await req.json();

  if (!phone || !code) {
    return NextResponse.json({ error: 'Phone and code required' }, { status: 400 });
  }

  const verifyServiceSid = process.env.TWILIO_VERIFY_SERVICE_SID;

  if (!verifyServiceSid) {
    // Dev mode: accept any code
    if (code === '000000') {
      return NextResponse.json({ status: 'approved' });
    }
    return NextResponse.json({ error: 'Invalid code' }, { status: 400 });
  }

  const accountSid = process.env.TWILIO_ACCOUNT_SID;
  const authToken = process.env.TWILIO_AUTH_TOKEN;

  const response = await fetch(
    `https://verify.twilio.com/v2/Services/${verifyServiceSid}/VerificationCheck`,
    {
      method: 'POST',
      headers: {
        Authorization: 'Basic ' + Buffer.from(`${accountSid}:${authToken}`).toString('base64'),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({ To: phone, Code: code }),
    },
  );

  const result = await response.json();

  if (result.status === 'approved') {
    return NextResponse.json({ status: 'approved' });
  }

  return NextResponse.json({ error: 'Invalid code' }, { status: 400 });
}
