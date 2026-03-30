import React, { useState, useCallback, useRef, useEffect } from 'react';
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
  const [photos, setPhotos] = useState([]);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [wsConnected, setWsConnected] = useState(false);

  const wsRef = useRef(null);

  const handleFolderSelected = useCallback(async (path) => {
    setFolderPath(path);
    setSelectedPhoto(null);
    setPhotos([]);
    setProgress({ current: 0, total: 0 });

    try {
      const res = await fetch(`${API_BASE}/api/photos`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: path }),
      });
      const data = await res.json();
      setPhotos(data.photos || []);
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
        setPhotos((prev) =>
          prev.map((p) =>
            p.photo_metadata.file_info.file_name === fileName
              ? { ...p, photo_metadata: { ...p.photo_metadata, ...updates } }
              : p
          )
        );
        if (selectedPhoto?.photo_metadata?.file_info?.file_name === fileName) {
          setSelectedPhoto((prev) => ({
            ...prev,
            photo_metadata: { ...prev.photo_metadata, ...updates },
          }));
        }
      }
    } catch (err) {
      console.error('Update failed:', err);
    }
  }, [folderPath, selectedPhoto]);

  // WebSocket message handlers
  const handleWsMessage = useCallback((data) => {
    switch (data.type) {
      case 'photo_result':
        setPhotos((prev) =>
          prev.map((p) =>
            p.photo_metadata.file_info.file_name === data.photo.photo_metadata.file_info.file_name
              ? data.photo
              : p
          )
        );
        // Update selected photo if it's the one that was updated
        setSelectedPhoto((prev) => {
          if (prev?.photo_metadata?.file_info?.file_name === data.photo.photo_metadata.file_info.file_name) {
            return data.photo;
          }
          return prev;
        });
        setProgress((prev) => ({
          current: prev.current + 1,
          total: prev.total,
        }));
        break;
      case 'progress':
        setProgress((prev) => ({
          current: data.current || prev.current,
          total: data.total || prev.total,
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

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <WebSocketManager
        url={`ws://127.0.0.1:${window.FLASK_PORT || 5000}`}
        onMessage={handleWsMessage}
        onConnectionChange={setWsConnected}
        ref={wsRef}
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
              photos={photos}
              selectedPhoto={selectedPhoto}
              onSelectPhoto={setSelectedPhoto}
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
            progress={progress}
            isProcessing={isProcessing}
            onStart={handleStartDetection}
            onCancel={handleCancelDetection}
            folderPath={folderPath}
            photos={photos}
          />
        </div>
      </div>
    </ThemeProvider>
  );
}
