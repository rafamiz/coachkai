import { NextRequest, NextResponse } from 'next/server';
import twilio from 'twilio';
import { getUserByPhone, isSubscriptionActive, processWhatsAppMessage } from '@nutricoach/core';

function twiml(message: string): NextResponse {
  // Escape XML special chars to avoid breaking TwiML
  const escaped = message
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  const xml = `<?xml version="1.0" encoding="UTF-8"?><Response><Message>${escaped}</Message></Response>`;
  return new NextResponse(xml, {
    status: 200,
    headers: { 'Content-Type': 'text/xml' },
  });
}

async function downloadTwilioMedia(
  mediaUrl: string,
  accountSid: string,
  authToken: string,
): Promise<{ base64: string; mimeType: string } | null> {
  try {
    const res = await fetch(mediaUrl, {
      headers: {
        Authorization: 'Basic ' + Buffer.from(`${accountSid}:${authToken}`).toString('base64'),
      },
    });
    if (!res.ok) return null;
    const contentType = res.headers.get('content-type') || 'image/jpeg';
    const mimeType = contentType.split(';')[0].trim();
    const buffer = await res.arrayBuffer();
    const base64 = Buffer.from(buffer).toString('base64');
    return { base64, mimeType };
  } catch {
    return null;
  }
}

export async function POST(req: NextRequest) {
  const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN!;
  const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID!;
  const APP_URL = process.env.NEXT_PUBLIC_APP_URL || process.env.APP_URL || 'https://nutricoach-one.vercel.app';

  try {
    // Parse form-encoded body from Twilio
    const text = await req.text();
    const params = new URLSearchParams(text);
    const body: Record<string, string> = {};
    params.forEach((v, k) => { body[k] = v; });

    // Validate Twilio signature
    const signature = req.headers.get('x-twilio-signature') || '';
    const url = req.url;
    const isValid = twilio.validateRequest(TWILIO_AUTH_TOKEN, signature, url, body);

    if (!isValid && process.env.NODE_ENV === 'production') {
      return new NextResponse('Forbidden', { status: 403 });
    }

    // Extract phone number (strip "whatsapp:" prefix)
    const phone = (body.From || '').replace('whatsapp:', '').trim();

    if (!phone) {
      return twiml('No se pudo identificar tu número.');
    }

    // Look up user in Supabase by phone number
    const user = await getUserByPhone(phone);

    // Check active subscription if user exists
    const hasActiveSub = user ? await isSubscriptionActive(user.id) : false;

    if (!user || !hasActiveSub) {
      // No user or no active subscription → welcome message + onboarding link
      const onboardingUrl = `${APP_URL}/onboarding?phone=${encodeURIComponent(phone)}`;
      return twiml(
        `👋 ¡Hola! Soy tu coach nutricional con IA.\n\n` +
        `Para empezar, completá tu perfil acá:\n${onboardingUrl}`
      );
    }

    // Determine if there's a photo
    const numMedia = parseInt(body.NumMedia || '0', 10);
    const mediaUrl = numMedia > 0 ? body.MediaUrl0 : undefined;
    const messageText = body.Body || '';

    let imageBase64: string | undefined;
    let imageMimeType: string | undefined;

    if (mediaUrl) {
      const media = await downloadTwilioMedia(mediaUrl, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN);
      if (media) {
        imageBase64 = media.base64;
        imageMimeType = media.mimeType;
      }
    }

    // Process via AI (Gemini) with full context and conversation history
    const { formattedReply } = await processWhatsAppMessage(
      user,
      messageText,
      imageBase64,
      imageMimeType,
      mediaUrl,
    );

    return twiml(formattedReply);
  } catch (error) {
    console.error('WhatsApp webhook error:', error);
    return twiml('Hubo un error procesando tu mensaje. Intentá de nuevo en unos minutos.');
  }
}
