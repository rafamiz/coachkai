import { NextRequest, NextResponse } from 'next/server';
import {
  getWhatsAppProvider,
  getUserByPhone,
  processWhatsAppMessage,
  sendWhatsAppReply,
  isSubscriptionActive,
  getServiceClient,
} from '@nutricoach/core';

// Meta Cloud API webhook verification
export async function GET(req: NextRequest) {
  const mode = req.nextUrl.searchParams.get('hub.mode');
  const token = req.nextUrl.searchParams.get('hub.verify_token');
  const challenge = req.nextUrl.searchParams.get('hub.challenge');

  if (mode === 'subscribe' && token === process.env.META_VERIFY_TOKEN) {
    return new NextResponse(challenge, { status: 200 });
  }
  return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
}

export async function POST(req: NextRequest) {
  try {
    const provider = getWhatsAppProvider();
    const contentType = req.headers.get('content-type') || '';
    let body: unknown;
    let rawBody: string;

    if (contentType.includes('application/x-www-form-urlencoded')) {
      rawBody = await req.text();
      const params = new URLSearchParams(rawBody);
      body = Object.fromEntries(params.entries());
    } else {
      rawBody = await req.text();
      body = JSON.parse(rawBody);
    }

    // Validate signature
    const headers: Record<string, string> = {};
    req.headers.forEach((value, key) => { headers[key] = value; });

    if (!provider.validateWebhookSignature(rawBody, headers)) {
      return NextResponse.json({ error: 'Invalid signature' }, { status: 401 });
    }

    const message = provider.parseIncomingWebhook(body, headers);
    if (!message) {
      return NextResponse.json({ status: 'no_message' });
    }

    // Find user
    const user = await getUserByPhone(message.from);
    if (!user) {
      const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://nutricoach.app';
      await provider.sendText(
        message.from,
        `Hey! \u{1F44B} Welcome to NutriCoach!\n\nTo get started, complete your profile:\n${appUrl}/onboarding`,
      );
      return NextResponse.json({ status: 'new_user' });
    }

    if (!user.onboarding_completed) {
      const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://nutricoach.app';
      await provider.sendText(
        message.from,
        `Almost there! Finish setting up your profile:\n${appUrl}/onboarding`,
      );
      return NextResponse.json({ status: 'onboarding_incomplete' });
    }

    // Check subscription
    const isActive = await isSubscriptionActive(user.id);
    if (!isActive) {
      const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://nutricoach.app';
      await provider.sendText(
        message.from,
        `Your trial has ended. Renew your subscription:\n${appUrl}/dashboard/settings`,
      );
      return NextResponse.json({ status: 'subscription_expired' });
    }

    // Handle image if present
    let imageBase64: string | undefined;
    let imageMimeType: string | undefined;
    let photoUrl: string | undefined;
    let photoStoragePath: string | undefined;

    if (message.type === 'image' && (message.mediaId || message.mediaUrl)) {
      const mediaId = message.mediaId || message.mediaUrl!;
      const { buffer, mimeType } = await provider.downloadMedia(mediaId);
      imageBase64 = buffer.toString('base64');
      imageMimeType = mimeType;

      // Upload to Supabase Storage
      const storagePath = `${user.id}/${Date.now()}.jpg`;
      const supabase = getServiceClient();
      await supabase.storage.from('meal-photos').upload(storagePath, buffer, {
        contentType: mimeType,
      });
      const { data: urlData } = supabase.storage.from('meal-photos').getPublicUrl(storagePath);
      photoUrl = urlData.publicUrl;
      photoStoragePath = storagePath;
    }

    // Process message
    const { formattedReply } = await processWhatsAppMessage(
      user,
      message.text || '',
      imageBase64,
      imageMimeType,
      photoUrl,
      photoStoragePath,
    );

    // Send reply
    await sendWhatsAppReply(user.phone, formattedReply);

    return NextResponse.json({ status: 'ok' });
  } catch (error) {
    console.error('WhatsApp webhook error:', error);
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}
