import { contextBridge, ipcRenderer } from "electron";
import type { PaperFactoryApi } from "../shared/api.js";

const api: PaperFactoryApi = {
  request: (method, path, body) => ipcRenderer.invoke("paperfactory:request", method, path, body),
  getRuntimeInfo: () => ipcRenderer.invoke("paperfactory:runtime"),
  openExternal: (url) => ipcRenderer.invoke("paperfactory:external", url),
  saveArtifact: (path) => ipcRenderer.invoke("paperfactory:artifact-save", path),
  openArtifact: (path) => ipcRenderer.invoke("paperfactory:artifact-open", path),
};
contextBridge.exposeInMainWorld("paperFactory", Object.freeze(api));
