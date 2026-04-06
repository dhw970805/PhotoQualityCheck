const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');

let mainWindow;
let flaskProcess;
const FLASK_PORT = 5000;

function findPython() {
  const candidates = ['python', 'python3'];
  // On Windows, try common paths
  if (process.platform === 'win32') {
    candidates.push(
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe'),
    );
  }
  return candidates;
}

function waitForPort(port, maxRetries = 30) {
  return new Promise((resolve, reject) => {
    let retries = 0;
    const check = () => {
      const socket = net.createConnection(port, '127.0.0.1', () => {
        socket.destroy();
        resolve();
      });
      socket.on('error', () => {
        retries++;
        if (retries >= maxRetries) {
          reject(new Error('Flask server failed to start'));
        } else {
          setTimeout(check, 1000);
        }
      });
      socket.setTimeout(1000);
    };
    check();
  });
}

async function startFlask() {
  if (app.isPackaged) {
    // --- Packaged mode: use PyInstaller-built executable ---
    const exeName = process.platform === 'win32' ? 'flask_server.exe' : 'flask_server';
    const exePath = path.join(process.resourcesPath, 'flask_server', exeName);

    if (!fs.existsSync(exePath)) {
      throw new Error(`Flask server not found at: ${exePath}`);
    }

    const userDataDir = app.getPath('userData');

    flaskProcess = spawn(exePath, [], {
      cwd: userDataDir,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        FLASK_PORT: String(FLASK_PORT),
        FLASK_LOG_DIR: userDataDir,
      },
    });
  } else {
    // --- Dev mode: find system Python and run app.py ---
    const candidates = findPython();
    let pythonCmd = 'python';

    for (const cmd of candidates) {
      try {
        const { execSync } = require('child_process');
        execSync(`"${cmd}" --version`, { stdio: 'pipe' });
        pythonCmd = cmd;
        break;
      } catch {
        continue;
      }
    }

    const backendDir = path.join(__dirname, '..', 'backend');
    flaskProcess = spawn(pythonCmd, ['app.py'], {
      cwd: backendDir,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, FLASK_PORT: String(FLASK_PORT) },
    });
  }

  flaskProcess.stdout.on('data', (data) => {
    console.log(`[Flask] ${data}`);
  });

  flaskProcess.stderr.on('data', (data) => {
    console.error(`[Flask ERR] ${data}`);
  });

  flaskProcess.on('close', (code) => {
    console.log(`Flask process exited with code ${code}`);
  });

  await waitForPort(FLASK_PORT);
  console.log('Flask server is ready');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#121212',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
      devTools: true,
    },
  });

  // dev: load from webpack dev server; prod: load from dist/index.html
  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  }); 
}

// IPC handlers
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

app.whenReady().then(async () => {
  try {
    await startFlask();
  } catch (err) {
    console.error('Failed to start Flask:', err.message);
  }
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (flaskProcess) {
    flaskProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (flaskProcess) {
    flaskProcess.kill();
  }
});
