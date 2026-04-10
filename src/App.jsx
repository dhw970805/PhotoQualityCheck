import React, { useState, useCallback, useMemo } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Toolbar from './components/Toolbar';
import FilterBar from './components/FilterBar';
import PhotoGrid from './components/PhotoGrid';
import DetailPanel from './components/DetailPanel';
import StatusBar from './components/StatusBar';
import WebSocketManager from './components/WebSocketManager';
import usePhotoStore from './hooks/usePhotoStore';
import * as api from './services/api';

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

export default function App() {
  const [folderPath, setFolderPath] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [importProgress, setImportProgress] = useState({ current: 0, total: 0 });
  const [wsConnected, setWsConnected] = useState(false);
  const [filterTags, setFilterTags] = useState(new Set());

  const photos = usePhotoStore();

  const handleFolderSelected = useCallback(async (path) => {
    setFolderPath(path);
    setProgress({ current: 0, total: 0 });

    try {
      const data = await api.loadPhotos(path);
      photos.loadPhotos(data.photos || []);
    } catch (err) {
      console.error('Failed to load photos:', err);
    }
  }, [photos]);

  const handleStartDetection = useCallback(async () => {
    if (!folderPath) return;
    setIsProcessing(true);
    try {
      const data = await api.startDetection(folderPath);
      setProgress({ current: 0, total: data.total || 0 });
    } catch (err) {
      console.error('Failed to start detection:', err);
      setIsProcessing(false);
    }
  }, [folderPath]);

  const handleCancelDetection = useCallback(async () => {
    try {
      await api.cancelDetection();
    } catch (err) {
      console.error('Failed to cancel:', err);
    }
    setIsProcessing(false);
  }, []);

  const handleExport = useCallback(async () => {
    if (!folderPath) return;

    // Check for photos that are "需复核" but not "合格"
    let hasUnreviewed = false;
    for (const p of photos.photoMap.values()) {
      const qualities = p.photo_metadata?.quality || [];
      if (qualities.includes('需复核') && !qualities.includes('合格')) {
        hasUnreviewed = true;
        break;
      }
    }
    if (hasUnreviewed) {
      const proceed = window.confirm('仍有需复核照片（未通过）未被导出，是否继续？');
      if (!proceed) return;
    }

    try {
      const data = await api.exportPhotos(folderPath);
      if (data.success) {
        alert(`导出完成！\n合格: ${data.summary?.合格 || 0} 张\n需复核: ${data.summary?.需复核 || 0} 张`);
      } else {
        alert(`导出失败: ${data.error || '未知错误'}`);
      }
    } catch (err) {
      console.error('Export failed:', err);
    }
  }, [folderPath, photos.photoMap]);

  const handleRetry = useCallback(async (fileName) => {
    try {
      await api.retryPhoto(fileName, folderPath);
    } catch (err) {
      console.error('Retry failed:', err);
    }
  }, [folderPath]);

  const handleUpdateResult = useCallback(async (fileName, updates) => {
    try {
      await api.updateResult(fileName, folderPath, updates);
      photos.patchPhoto(fileName, updates);
    } catch (err) {
      console.error('Update failed:', err);
    }
  }, [folderPath, photos]);

  // WebSocket message handlers
  const handleWsMessage = useCallback((data) => {
    switch (data.type) {
      case 'photo_result': {
        const fileName = data.photo.photo_metadata.file_info.file_name;
        photos.updatePhoto(fileName, data.photo);
        break;
      }
      case 'progress':
        setProgress((prev) => ({
          current: data.current ?? prev.current,
          total: data.total ?? prev.total,
        }));
        break;
      case 'import_progress':
        setImportProgress({ current: data.current ?? 0, total: data.total ?? 0 });
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
  }, [photos]);

  const filteredPhotoNames = useMemo(() => {
    return photos.getFilteredNames(filterTags);
  }, [photos, filterTags]);

  const statusCounts = useMemo(() => {
    return photos.getStatusCounts(filteredPhotoNames.length);
  }, [photos, filteredPhotoNames.length]);

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <WebSocketManager
        url={api.getWsUrl()}
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
        {folderPath && (
          <FilterBar filterTags={filterTags} onFilterChange={setFilterTags} />
        )}
        <div className="main-content">
          <div className="photo-grid-area">
            <PhotoGrid
              photoNames={filteredPhotoNames}
              photoMap={photos.photoMap}
              photoVersion={photos.photoVersion}
              selectedFileName={photos.selectedFileName}
              onSelectPhoto={photos.selectPhoto}
              onUpdateResult={handleUpdateResult}
            />
          </div>
          <div className="detail-panel-area">
            <DetailPanel
              photo={photos.selectedPhoto}
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
            importProgress={importProgress}
          />
        </div>
      </div>
    </ThemeProvider>
  );
}
