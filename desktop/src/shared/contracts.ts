export interface AppError {
  code: string;
  message: string;
  action: 'retry' | 'sign-in' | 'usage' | null;
}

export interface AppSnapshot {
  version: string;
  session: {
    connected: boolean;
    sharing: boolean;
    profileId?: string;
    account?: { email?: string; name?: string };
  };
  profiles: Array<{ id: string; label: string; email?: string; connected: boolean; sharing: boolean; pending?: boolean }>;
  models: Array<{ slug: string; displayName: string }>;
  busy: 'sign-in' | 'select-profile' | 'disconnect' | 'models' | 'verify' | null;
  error: AppError | null;
  verification: { model: string; text: string; completedAt: string } | null;
}

import type { ResearchApi } from './research.js';

export interface PaperFactoryApi extends ResearchApi {
  snapshot(): Promise<AppSnapshot>;
  signIn(profileId?: string): Promise<AppSnapshot>;
  cancel(): Promise<AppSnapshot>;
  disconnect(): Promise<AppSnapshot>;
  selectProfile(profileId: string): Promise<AppSnapshot>;
  refreshModels(): Promise<AppSnapshot>;
  verify(model: string): Promise<AppSnapshot>;
  openUsage(): Promise<void>;
  onSnapshot(listener: (snapshot: AppSnapshot) => void): () => void;
}
