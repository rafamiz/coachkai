import crypto from 'crypto';
import { WhatsAppProvider } from './provider';
import { IncomingMessage } from '../types/whatsapp';

export class MetaProvider implements WhatsAppProvider {
  private token: string;
  private phoneNumberId: string;
  private appSecret: string;
  private apiBase = 'https://graph.facebook.com/v21.0';

  constructor() {
    this.token = process.env.META_WHATSAPP_TOKEN!;
    this.phoneNumberId = process.env.META_WHATSAPP_PHONE_ID!;
    this.appSecret = process.env.META_APP_SECRET!;
  }

  async sendText(to: string, body: string): Promise<void> {
    await fetch(`${this.apiBase}/${this.phoneNumberId}/messages`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messaging_product: 'whatsapp',
        to,
        type: 'text',
        text: { body },
      }),
    });
  }

  async sendImage(to: string, imageUrl: string, caption?: string): Promise<void> {
    await fetch(`${this.apiBase}/${this.phoneNumberId}/messages`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messaging_product: 'whatsapp',
        to,
        type: 'image',
        image: { link: imageUrl, caption },
      }),
    });
  }

  async sendTemplate(to: string, templateName: string, params: Record<string, string>): Promise<void> {
    const components = Object.entries(params).length > 0
      ? [{
          type: 'body',
          parameters: Object.values(params).map((v) => ({ type: 'text', text: v })),
        }]
      : [];

    await fetch(`${this.apiBase}/${this.phoneNumberId}/messages`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messaging_product: 'whatsapp',
        to,
        type: 'template',
        template: { name: templateName, language: { code: 'en' }, components },
      }),
    });
  }

  parseIncomingWebhook(body: Record<string, unknown>): IncomingMessage | null {
    try {
      const entry = (body.entry as Array<Record<string, unknown>>)?.[0];
      const changes = (entry?.changes as Array<Record<string, unknown>>)?.[0];
      const value = changes?.value as Record<string, unknown>;
      const messages = (value?.messages as Array<Record<string, unknown>>);
      if (!messages?.length) return null;

      const msg = messages[0];
      const from = msg.from as string;
      const type = msg.type as string;
      const timestamp = new Date(parseInt(msg.timestamp as string, 10) * 1000);

      let text: string | undefined;
      let mediaId: string | undefined;

      if (type === 'text') {
        text = (msg.text as Record<string, string>)?.body;
      } else if (type === 'image') {
        mediaId = (msg.image as Record<string, string>)?.id;
        text = (msg.image as Record<string, string>)?.caption;
      }

      return {
        from,
        type: type === 'image' ? 'image' : 'text',
        text,
        mediaId,
        timestamp,
        messageId: msg.id as string,
      };
    } catch {
      return null;
    }
  }

  validateWebhookSignature(body: string, headers: Record<string, string>): boolean {
    const signature = headers['x-hub-signature-256'];
    if (!signature) return false;

    const expected = 'sha256=' + crypto
      .createHmac('sha256', this.appSecret)
      .update(body)
      .digest('hex');

    return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
  }

  async downloadMedia(mediaId: string): Promise<{ buffer: Buffer; mimeType: string }> {
    // Step 1: Get media URL
    const urlRes = await fetch(`${this.apiBase}/${mediaId}`, {
      headers: { Authorization: `Bearer ${this.token}` },
    });
    const urlData = await urlRes.json() as { url: string; mime_type: string };

    // Step 2: Download
    const mediaRes = await fetch(urlData.url, {
      headers: { Authorization: `Bearer ${this.token}` },
    });
    const buffer = Buffer.from(await mediaRes.arrayBuffer());
    return { buffer, mimeType: urlData.mime_type || 'image/jpeg' };
  }
}
