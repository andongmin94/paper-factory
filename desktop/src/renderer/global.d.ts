import type { PaperFactoryApi } from "../shared/contracts";

declare global {
  interface Window {
    paperFactory: PaperFactoryApi;
  }
}

export {};
