import React, { useState, useCallback, useRef, useMemo } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Toolbar from './components/Toolbar';
import PhotoGrid from './components/PhotoGrid';
import DetailPanel from './components/DetailPanel';
import StatusBar from './components/StatusBar';
import WebSocketManager from './components/WebSocketManager';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#ce93d8',
    },
    background: {
      default: '#121212',
      paper: '#1E1E1E',
    },
  },
  typography: {
    fontFamily: '"Segoe UI", "Microsoft YaHei", sans-serif',
  },
});

const API_BASE = 'http://127.0.0.1:5000';

export default function App() {
  const [folderPath, setFolderPath] = useState(null);
  // photoNames: string[] — ordered file names (stable reference, only changes on folder load)
  // photoMap: Map<string, object> — keyed by file_name (mutated in place, same reference)
  // photoVersion: number — bumped when a photo is updated (triggers Grid re-check)
  const [photoNames, setPhotoNames] = useState([]);
  const [photoMap, setPhotoMap] = useState(() => new Map());
  const [photoVersion, setPhotoVersion] = useState(0);
  const [selectedFileName, setSelectedFileName] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [wsConnected, setWsConnected] = useState(false);

  const photoMapRef = useRef(photoMap);
  photoMapRef.current = photoMap;

  const selectedPhoto = selectedFileName ? photoMap.get(selectedFileName) : null;

  const handleFolderSelected = useCallback(async (path) => {
    setFolderPath(path);
    setSelectedFileName(null);
    setPhotoNames([]);
    setPhotoMap(() => new Map());
    setPhotoVersion(0);
    setProgress({ current: 0, total: 0 });

    try {
      const res = await fetch(`${API_BASE}/api/photos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: path }),
      });
      const data = await res.json();
      const list = data.photos || [];
      const names = list.map((p) => p.photo_metadata.file_info.file_name);
      const map = new Map();
      list.forEach((p) => map.set(p.photo_metadata.file_info.file_name, p));
      setPhotoNames(names);
      setPhotoMap(() => map);
    } catch (err) {
      console.error('Failed to load photos:', err);
    }
  }, []);

  const handleStartDetection = useCallback(async () => {
    if (!folderPath) return;
    setIsProcessing(true);
    try {
      const res = await fetch(`${API_BASE}/api/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath }),
      });
      const data = await res.json();
      setProgress({ current: 0, total: data.total || 0 });
    } catch (err) {
      console.error('Failed to start detection:', err);
      setIsProcessing(false);
    }
  }, [folderPath]);

  const handleCancelDetection = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/api/cancel`, { method: 'POST' });
    } catch (err) {
      console.error('Failed to cancel:', err);
    }
    setIsProcessing(false);
  }, []);

  const handleExport = useCallback(async () => {
    if (!folderPath) return;
    try {
      const res = await fetch(`${API_BASE}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath }),
      });
      const data = await res.json();
      if (data.success) {
        alert(`导出完成！\n合格: ${data.summary?.合格 || 0} 张\n需复核: ${data.summary?.需复核 || 0} 张`);
      } else {
        alert(`导出失败: ${data.error || '未知错误'}`);
      }
    } catch (err) {
      console.error('Export failed:', err);
    }
  }, [folderPath]);

  const handleRetry = useCallback(async (fileName) => {
    try {
      await fetch(`${API_BASE}/api/retry/${encodeURIComponent(fileName)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath }),
      });
    } catch (err) {
      console.error('Retry failed:', err);
    }
  }, [folderPath]);

  const handleUpdateResult = useCallback(async (fileName, updates) => {
    try {
      const res = await fetch(`${API_BASE}/api/update-result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath, file_name: fileName, updates }),
      });
      const data = await res.json();
      if (data.success) {
        setPhotoMap((prev) => {
          const next = new Map(prev);
          const photo = next.get(fileName);
          if (photo) {
            next.set(fileName, {
              ...photo,
              photo_metadata: { ...photo.photo_metadata, ...updates },
            });
          }
          return next;
        });
        setPhotoVersion((v) => v + 1);
      }
    } catch (err) {
      console.error('Update failed:', err);
    }
  }, [folderPath]);

  const handleSelectPhoto = useCallback((photo) => {
    setSelectedFileName(photo?.photo_metadata?.file_info?.file_name || null);
  }, []);

  // WebSocket message handlers
  const handleWsMessage = useCallback((data) => {
    switch (data.type) {
      case 'photo_result': {
        const fileName = data.photo.photo_metadata.file_info.file_name;
        setPhotoMap((prev) => {
          const next = new Map(prev);
          next.set(fileName, data.photo);
          return next;
        });
        setPhotoVersion((v) => v + 1);
        break;
      }
      case 'progress':
        setProgress((prev) => ({
          current: data.current ?? prev.current,
          total: data.total ?? prev.total,
        }));
        break;
      case 'complete':
        setIsProcessing(false);
        setProgress((prev) => ({ ...prev, current: prev.total }));
        break;
      case 'error':
        setIsProcessing(false);
        console.error('Pipeline error:', data.message);
        break;
      default:
        break;
    }
  }, []);

  // StatusBar needs counts — compute from photoMap efficiently
  const statusCounts = useMemo(() => {
    let detected = 0;
    for (const p of photoMap.values()) {
      if (p.photo_metadata?.status !== '未检测') detected++;
    }
    return { total: photoNames.length, detected, pending: photoNames.length - detected };
  }, [photoNames.length, photoVersion]);

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <WebSocketManager
        url={`ws://127.0.0.1:${window.FLASK_PORT || 5000}`}
        onMessage={handleWsMessage}
        onConnectionChange={setWsConnected}
      />
      <div className="app-container">
        <Toolbar
          folderPath={folderPath}
          onFolderSelect={handleFolderSelected}
          onExport={handleExport}
          wsConnected={wsConnected}
        />
        <div className="main-content">
          <div className="photo-grid-area">
            <PhotoGrid
              photoNames={photoNames}
              photoMap={photoMap}
              photoVersion={photoVersion}
              selectedFileName={selectedFileName}
              onSelectPhoto={handleSelectPhoto}
            />
          </div>
          <div className="detail-panel-area">
            <DetailPanel
              photo={selectedPhoto}
              onUpdateResult={handleUpdateResult}
              onRetry={handleRetry}
              isProcessing={isProcessing}
            />
          </div>
        </div>
        <div className="status-bar-area">
          <StatusBar
            statusCounts={statusCounts}
            isProcessing={isProcessing}
            onStart={handleStartDetection}
            onCancel={handleCancelDetection}
            folderPath={folderPath}
          />
        </div>
      </div>
    </ThemeProvider>
  );
}
