import { IncomingMessage } from '../types/whatsapp';

export interface WhatsAppProvider {
  sendText(to: string, body: string): Promise<void>;
  sendImage(to: string, imageUrl: string, caption?: string): Promise<void>;
  sendTemplate(to: string, templateName: string, params: Record<string, string>): Promise<void>;
  parseIncomingWebhook(body: unknown, headers: Record<string, string>): IncomingMessage | null;
  validateWebhookSignature(body: string, headers: Record<string, string>): boolean;
  downloadMedia(mediaId: string): Promise<{ buffer: Buffer; mimeType: string }>;
}

export function getWhatsAppProvider(): WhatsAppProvider {
  const provider = process.env.WHATSAPP_PROVIDER || 'twilio';
  if (provider === 'meta') {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { MetaProvider } = require('./meta');
    return new MetaProvider();
  }
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { TwilioProvider } = require('./twilio');
  return new TwilioProvider();
}
