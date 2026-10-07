import { app, BrowserWindow, dialog, ipcMain, safeStorage, shell } from 'electron';
import { createChatGPT, CHATGPT_USAGE_URL } from '@siwc/local';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { ConnectionController } from './connection.js';
import { EngineBridge, EngineError } from './engine.js';
import { ResearchController, readSupportingEvidence } from './research.js';
import type { CreateResearchInput } from '../shared/research.js';
import { listPublicRepositories } from './repositories.js';
import { artifactFormats, readVerifiedArtifact, saveArtifactWithDialog, type ResolvedArtifact } from './artifacts.js';

app.setName('Paper Factory');
// Own standalone data only; past plugin studies are not recovered by this app.
app.setPath('userData', !app.isPackaged && process.env.PF_DESKTOP_DATA_DIR
  ? resolve(process.env.PF_DESKTOP_DATA_DIR)
  : join(app.getPath('appData'), 'Paper Factory Standalone'));
const root = dirname(fileURLToPath(import.meta.url));
const renderer = pathToFileURL(join(root, 'renderer', 'index.html')).href;
let window: BrowserWindow | undefined;
let controller: ConnectionController | undefined;
let research: ResearchController | undefined;
let quitApproved = false;
let quitTask: Promise<void> | undefined;
let saveTask: Promise<boolean> | undefined;
let createWindow: (() => Promise<void>) | undefined;

function showWindow() {
  if (window && !window.isDestroyed()) {
    if (window.isMinimized()) window.restore();
    window.focus();
  } else if (createWindow) {
    void createWindow();
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', showWindow);
  // Finish ESM entry evaluation before waiting for Electron's ready lifecycle.
  void app.whenReady().then(async () => {
    const client = createChatGPT({
      appName: 'Paper Factory', appId: 'paper-factory', redirectPort: 0,
      storageDir: join(app.getPath('userData'), 'chatgpt'), sendHostId: true,
      credentialEncryption: {
        id: 'electron-safe-storage-v1',
        isAvailable: () => ['win32', 'darwin'].includes(process.platform) && safeStorage.isEncryptionAvailable(),
        encrypt: (plaintext) => safeStorage.encryptString(plaintext),
        decrypt: (ciphertext) => safeStorage.decryptString(Buffer.from(ciphertext)),
      },
      openBrowser: async (url) => {
        if (new URL(url).origin !== 'https://auth.openai.com') throw new Error('Authorization origin rejected');
        await shell.openExternal(url);
      },
    });
    controller = new ConnectionController(client, app.getVersion(), join(app.getPath('userData'), 'evidence'), (snapshot) => {
      if (window && !window.isDestroyed()) window.webContents.send('connection:changed', snapshot);
    });
    const runtimeRoot = app.isPackaged ? join(process.resourcesPath, 'runtime') : join(app.getAppPath(), 'runtime', `${process.platform}-${process.arch}`);
    const engineHome = join(app.getPath('userData'), 'engine');
    const engine = new EngineBridge(runtimeRoot, engineHome, join(app.getAppPath(), 'third-party', 'runtime-inventory-binding.json'));
    research = new ResearchController(client, engine, join(app.getPath('userData'), 'research'), snapshot => {
      if (window && !window.isDestroyed()) window.webContents.send('research:changed', snapshot);
    });
    const requestQuit = () => {
      if (quitTask || quitApproved) return;
      quitTask = (async () => {
        let retry = false;
        try {
          // A native save dialog and its atomic file commit must settle before engine shutdown.
          await saveTask?.catch(() => {});
          await research!.shutdown();
          await controller!.shutdown();
          quitApproved = true;
          app.quit();
        } catch {
          if (window && !window.isDestroyed()) {
            const choice = await dialog.showMessageBox(window, {
              type: 'error', title: '앱 종료를 완료하지 못했습니다.',
              message: '실험 종료 또는 기록 보존을 확인하지 못해 앱을 열어 두었습니다.',
              detail: '결과 화면의 오류와 정리 상태를 확인해 주세요. 정리를 다시 시도하면 기록 보존과 엔진 종료를 다시 확인합니다.',
              buttons: ['앱으로 돌아가기', '정리 다시 시도'], defaultId: 0, cancelId: 0,
            });
            retry = choice.response === 1;
          }
        } finally { quitTask = undefined; }
        if (retry) requestQuit();
      })();
    };
    createWindow = async () => {
      const nextWindow = new BrowserWindow({ width: 1020, height: 850, minWidth: 720, minHeight: 640,
        title: 'Paper Factory', backgroundColor: '#ffffff', autoHideMenuBar: true,
        webPreferences: { preload: join(root, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true },
      });
      window = nextWindow;
      nextWindow.on('close', event => {
        if (quitApproved) return;
        event.preventDefault();
        requestQuit();
      });
      nextWindow.on('closed', () => { if (window === nextWindow) window = undefined; });
      nextWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
      nextWindow.webContents.on('will-navigate', (event) => event.preventDefault());
      nextWindow.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
      nextWindow.webContents.session.setPermissionCheckHandler(() => false);
      await nextWindow.loadFile(join(root, 'renderer', 'index.html'));
    };

    const handle = (channel: string, fn: (...args: unknown[]) => unknown) => ipcMain.handle(channel, (event, ...args: unknown[]) => {
      if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || event.senderFrame.url !== renderer) {
        throw new Error('Request denied');
      }
      if (quitTask && !['connection:snapshot', 'research:snapshot'].includes(channel)) {
        throw new EngineError('APP_CLOSING', '앱 종료를 위해 작업과 기록을 정리하고 있습니다.');
      }
      return fn(...args);
    });
    const noArgs = (fn: () => unknown) => (...args: unknown[]) => {
      if (args.length) throw new Error('Invalid request');
      return fn();
    };
    const identifier = (value: unknown, kind: 'profile' | 'model') => {
      if (typeof value !== 'string' || !value || value.length > 200 || /[\u0000-\u001f]/.test(value) ||
        (kind === 'profile' && !/^[a-zA-Z0-9-]{1,100}$/.test(value))) throw new Error('Invalid request');
      return value;
    };
    const connectionIdle = () => {
      if (saveTask) throw new EngineError('ARTIFACT_SAVING', '결과 파일 저장이 끝난 뒤 계정 작업을 시작하세요.');
      if (research!.snapshot().busy) throw new EngineError('RESEARCH_BUSY', '연구 진행 중에는 계정 연결과 모델 검증을 변경할 수 없습니다.');
    };
    handle('connection:snapshot', noArgs(() => controller!.snapshot()));
    handle('connection:sign-in', (...args) => {
      connectionIdle();
      if (args.length > 1) throw new Error('Invalid request');
      return controller!.signIn(args[0] === undefined ? undefined : identifier(args[0], 'profile'));
    });
    handle('connection:cancel', noArgs(() => controller!.cancel()));
    handle('connection:disconnect', noArgs(() => { connectionIdle(); return controller!.disconnect(); }));
    handle('connection:select-profile', (...args) => {
      connectionIdle();
      if (args.length !== 1) throw new Error('Invalid request');
      return controller!.selectProfile(identifier(args[0], 'profile'));
    });
    handle('connection:models', noArgs(() => { connectionIdle(); return controller!.refreshModels(); }));
    handle('connection:verify', (...args) => {
      connectionIdle();
      if (args.length !== 1) throw new Error('Invalid request');
      return controller!.verify(identifier(args[0], 'model'));
    });
    handle('connection:usage', noArgs(() => shell.openExternal(CHATGPT_USAGE_URL)));
    const researchId = (value: unknown) => {
      if (typeof value !== 'string' || !/^research-[a-f0-9]{12}$/.test(value)) throw new Error('Invalid research id');
      return value;
    };
    const researchReady = () => {
      if (saveTask) throw new EngineError('ARTIFACT_SAVING', '결과 파일 저장이 끝난 뒤 연구 작업을 시작하세요.');
      if (controller!.isBusy()) throw new EngineError('CONNECTION_BUSY', '계정 작업과 연결 확인이 끝난 뒤 연구를 시작하세요.');
    };
    handle('research:snapshot', noArgs(() => research!.snapshot()));
    handle('research:repositories', (...args) => {
      if (args.length !== 1 || typeof args[0] !== 'string') throw new Error('Invalid account request');
      return listPublicRepositories(args[0]);
    });
    handle('research:runtime', noArgs(() => research!.checkRuntime()));
    handle('research:create', (...args) => {
      researchReady();
      const value = args[0] as CreateResearchInput;
      if (args.length !== 1 || !value || typeof value !== 'object' || Array.isArray(value) ||
        Object.keys(value).sort().join(',') !== 'goal,model,reviewerModel,source' ||
        typeof value.source !== 'string' || !/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(value.source) ||
        typeof value.goal !== 'string' || value.goal.trim().length < 8 || value.goal.length > 4000 || /[\u0000]/.test(value.goal)) throw new Error('Invalid research request');
      identifier(value.model, 'model'); identifier(value.reviewerModel, 'model');
      return research!.create(value);
    });
    handle('research:resume', (...args) => {
      researchReady();
      if (args.length !== 3) throw new Error('Invalid research request');
      return research!.resume(researchId(args[0]), identifier(args[1], 'model'), identifier(args[2], 'model'));
    });
    handle('research:revise-writing', (...args) => {
      researchReady();
      if (args.length !== 3) throw new Error('Invalid research request');
      return research!.reviseWriting(researchId(args[0]), identifier(args[1], 'model'), identifier(args[2], 'model'));
    });
    handle('research:improve-writing', (...args) => {
      researchReady();
      if (args.length !== 3) throw new Error('Invalid research request');
      return research!.improveWriting(researchId(args[0]), identifier(args[1], 'model'), identifier(args[2], 'model'));
    });
    handle('research:cancel', (...args) => {
      if (args.length !== 1) throw new Error('Invalid research request');
      return research!.cancel(researchId(args[0]));
    });
    handle('research:add-evidence', (...args) => {
      researchReady();
      if (args.length !== 1) throw new Error('Invalid research request');
      return research!.addEvidence(researchId(args[0]), async () => {
        const choice = await dialog.showOpenDialog(window!, {
          title: '추가 근거 선택', buttonLabel: '근거 가져오기',
          message: '원문 문서만 가져옵니다. 측정·프로토콜·리뷰 승인을 변경하거나 연구를 자동 재개하지 않습니다.',
          properties: ['openFile', 'multiSelections', 'dontAddToRecent'],
          filters: [{ name: 'UTF-8 근거 문서', extensions: ['md', 'txt', 'json'] }],
        });
        return choice.canceled ? null : readSupportingEvidence(choice.filePaths);
      });
    });
    const verifiedArtifact = async (args: unknown[]) => {
      if (args.length !== 2 || typeof args[1] !== 'string' || !Object.hasOwn(artifactFormats, args[1])) throw new Error('Invalid artifact request');
      const id = researchId(args[0]);
      const artifact = await engine.request<ResolvedArtifact>('artifact.resolve', { researchId: id, artifactId: args[1] });
      return readVerifiedArtifact(artifact, engineHome);
    };
    handle('research:open-artifact', async (...args) => {
      const artifact = await verifiedArtifact(args);
      const error = await shell.openPath(artifact.path);
      if (error) throw new Error('파일을 열 수 없습니다. 기본 문서 앱을 확인하세요.');
    });
    handle('research:artifact-folder', async (...args) => {
      const artifact = await verifiedArtifact(args);
      shell.showItemInFolder(artifact.path);
    });
    handle('research:save-artifact', (...args) => {
      researchReady();
      if (research!.snapshot().busy) throw new EngineError('RESEARCH_BUSY', '현재 연구 작업이 끝난 뒤 결과 파일을 저장하세요.');
      if (args.length !== 2 || typeof args[1] !== 'string' || !Object.hasOwn(artifactFormats, args[1])) throw new Error('Invalid artifact request');
      researchId(args[0]);
      saveTask = (async () => {
        const artifact = await verifiedArtifact(args);
        return saveArtifactWithDialog({
          artifact, artifactId: args[1] as string, researchId: args[0] as string,
          documentsPath: app.getPath('documents'), protectedRoot: app.getPath('userData'),
          chooseFile: options => dialog.showSaveDialog(window!, options),
          chooseDirectory: options => dialog.showOpenDialog(window!, options),
        });
      })().finally(() => { saveTask = undefined; });
      return saveTask;
    });
    await controller.initialize();
    app.on('activate', showWindow);
    app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
    app.on('before-quit', (event) => {
      if (quitApproved) return;
      event.preventDefault();
      requestQuit();
    });
    await createWindow();
    // Runtime absence must leave the connection UI available and actionable.
    void research.initialize().catch(() => {});
  }).catch(() => {
    dialog.showErrorBox('Paper Factory', '앱을 시작하지 못했습니다. 앱 설치와 저장 경로를 확인해 주세요.');
    app.exit(1);
  });
}
