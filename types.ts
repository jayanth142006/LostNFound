export enum AppState {
    LANDING = 'LANDING',
    LOST_FLOW = 'LOST_FLOW',
    FOUND_FLOW = 'FOUND_FLOW',
    VERIFICATION = 'VERIFICATION'
}

export interface ChatMessage {
    id: string;
    sender: 'user' | 'ai';
    text: string;
    timestamp: number;
    visualCues?: string[]; // Extracted details for the visualizer
}

export interface LostItemProfile {
    category: string;
    confidence: number;
    tags: string[];
    colorHex: string;
    lastSeen: string;
    generatedImage?: string;
    time?: string;
    days_since_loss?: number;
}

export interface FoundItem {
    id: string;
    description: string;
    location: string;
    imageUrl?: string;
    finderTrustScore: number;
}