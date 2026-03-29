import twilio from 'twilio';
import crypto from 'crypto';
import { WhatsAppProvider } from './provider';
import { IncomingMessage } from '../types/whatsapp';

export class TwilioProvider implements WhatsAppProvider {
  private client: twilio.Twilio;
  private fromNumber: string;
  private authToken: string;

  constructor() {
    const accountSid = process.env.TWILIO_ACCOUNT_SID!;
    this.authToken = process.env.TWILIO_AUTH_TOKEN!;
    this.fromNumber = process.env.TWILIO_WHATSAPP_NUMBER!;
    this.client = twilio(accountSid, this.authToken);
  }

  async sendText(to: string, body: string): Promise<void> {
    await this.client.messages.create({
      from: `whatsapp:${this.fromNumber}`,
      to: `whatsapp:${to}`,
      body,
    });
  }

  async sendImage(to: string, imageUrl: string, caption?: string): Promise<void> {
    await this.client.messages.create({
      from: `whatsapp:${this.fromNumber}`,
      to: `whatsapp:${to}`,
      mediaUrl: [imageUrl],
      body: caption || '',
    });
  }

  async sendTemplate(to: string, templateName: string, params: Record<string, string>): Promise<void> {
    // Twilio uses content templates
    await this.client.messages.create({
      from: `whatsapp:${this.fromNumber}`,
      to: `whatsapp:${to}`,
      body: `Template: ${templateName} - ${JSON.stringify(params)}`,
    });
  }

  parseIncomingWebhook(body: Record<string, string>): IncomingMessage | null {
    const from = body.From?.replace('whatsapp:', '') || '';
    if (!from) return null;

    const hasMedia = parseInt(body.NumMedia || '0', 10) > 0;

    return {
      from,
      type: hasMedia ? 'image' : 'text',
      text: body.Body || undefined,
      mediaUrl: hasMedia ? body.MediaUrl0 : undefined,
      mediaId: hasMedia ? body.MediaUrl0 : undefined,
      timestamp: new Date(),
      messageId: body.MessageSid || '',
    };
  }

  validateWebhookSignature(body: string, headers: Record<string, string>): boolean {
    const signature = headers['x-twilio-signature'];
    if (!signature) return false;

    const url = process.env.NEXT_PUBLIC_APP_URL + '/api/webhooks/whatsapp';
    const params = new URLSearchParams(body);
    const sortedParams: Record<string, string> = {};
    [...params.entries()].sort(([a], [b]) => a.localeCompare(b)).forEach(([k, v]) => {
      sortedParams[k] = v;
    });

    let dataString = url;
    for (const [key, value] of Object.entries(sortedParams)) {
      dataString += key + value;
    }

    const computed = crypto
      .createHmac('sha1', this.authToken)
      .update(Buffer.from(dataString, 'utf-8'))
      .digest('base64');

    return computed === signature;
  }

  async downloadMedia(mediaUrl: string): Promise<{ buffer: Buffer; mimeType: string }> {
    const response = await fetch(mediaUrl, {
      headers: {
        Authorization: 'Basic ' + Buffer.from(
          `${process.env.TWILIO_ACCOUNT_SID}:${this.authToken}`
        ).toString('base64'),
      },
    });
    const buffer = Buffer.from(await response.arrayBuffer());
    const mimeType = response.headers.get('content-type') || 'image/jpeg';
    return { buffer, mimeType };
  }
}
