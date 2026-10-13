import { contextBridge, ipcRenderer } from 'electron';
import type { AppSnapshot, PaperFactoryApi } from '../shared/contracts.js';
import type { ResearchSnapshot } from '../shared/research.js';

const api: PaperFactoryApi = {
  snapshot: () => ipcRenderer.invoke('connection:snapshot'),
  signIn: (profileId) => ipcRenderer.invoke('connection:sign-in', profileId),
  cancel: () => ipcRenderer.invoke('connection:cancel'),
  disconnect: () => ipcRenderer.invoke('connection:disconnect'),
  selectProfile: (profileId) => ipcRenderer.invoke('connection:select-profile', profileId),
  refreshModels: () => ipcRenderer.invoke('connection:models'),
  verify: (model) => ipcRenderer.invoke('connection:verify', model),
  openUsage: () => ipcRenderer.invoke('connection:usage'),
  researchSnapshot: () => ipcRenderer.invoke('research:snapshot'),
  checkRuntime: () => ipcRenderer.invoke('research:runtime'),
  createResearch: (input) => ipcRenderer.invoke('research:create', input),
  resumeResearch: (id, model, reviewerModel) => ipcRenderer.invoke('research:resume', id, model, reviewerModel),
  improveResearch: (id, model, reviewerModel) => ipcRenderer.invoke('research:improve', id, model, reviewerModel),
  requestRepositoryRevision: (researchId, feedback) => ipcRenderer.invoke('research:repository-revision', researchId, feedback),
  requestRepositoryPortfolio: (researchId) => ipcRenderer.invoke('research:repository-portfolio', researchId),
  reformatRepositoryPortfolioDraft: (researchId, venueId) => ipcRenderer.invoke('research:portfolio-format', researchId, venueId),
  correctRepositoryPortfolioLayout: (researchId, venueId) => ipcRenderer.invoke('research:portfolio-layout', researchId, venueId),
  exportRepositoryPortfolioAuthor: (researchId, venueId) => ipcRenderer.invoke('research:portfolio-author', researchId, venueId),
  admitRepositoryPortfolioEvidence: (researchId, packet) => ipcRenderer.invoke('research:portfolio-evidence', researchId, packet),
  reformatResearchDraft: (id) => ipcRenderer.invoke('research:reformat-draft', id),
  setResearchAuthorMetadata: (id, value) => ipcRenderer.invoke('research:author-metadata', id, value),
  cancelResearch: (id) => ipcRenderer.invoke('research:cancel', id),
  addResearchEvidence: (id) => ipcRenderer.invoke('research:add-evidence', id),
  saveArtifact: (id, artifactId) => ipcRenderer.invoke('research:save-artifact', id, artifactId),
  openArtifact: (id, artifactId) => ipcRenderer.invoke('research:open-artifact', id, artifactId),
  showArtifactFolder: (id, artifactId) => ipcRenderer.invoke('research:artifact-folder', id, artifactId),
  listPublicRepositories: (accountUrl) => ipcRenderer.invoke('research:repositories', accountUrl),
  onResearchSnapshot: (listener) => {
    const handler = (_event: Electron.IpcRendererEvent, snapshot: ResearchSnapshot) => listener(snapshot);
    ipcRenderer.on('research:changed', handler);
    return () => ipcRenderer.removeListener('research:changed', handler);
  },
  onSnapshot: (listener) => {
    const handler = (_event: Electron.IpcRendererEvent, snapshot: AppSnapshot) => listener(snapshot);
    ipcRenderer.on('connection:changed', handler);
    return () => ipcRenderer.removeListener('connection:changed', handler);
  },
};
contextBridge.exposeInMainWorld('paperFactory', api);
