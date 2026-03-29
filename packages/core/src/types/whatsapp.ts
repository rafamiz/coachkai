export interface IncomingMessage {
  from: string;
  type: 'text' | 'image' | 'audio' | 'location';
  text?: string;
  mediaId?: string;
  mediaUrl?: string;
  timestamp: Date;
  messageId: string;
}

export interface OutgoingMessage {
  to: string;
  body: string;
  mediaUrl?: string;
}
