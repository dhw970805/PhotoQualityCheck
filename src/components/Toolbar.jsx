import React from 'react';
import AppBar from '@mui/material/AppBar';
import MuiToolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import Box from '@mui/material/Box';

export default function Toolbar({ folderPath, onFolderSelect, onExport, wsConnected }) {
  const handleSelectFolder = async () => {
    if (window.electronAPI?.selectFolder) {
      const path = await window.electronAPI.selectFolder();
      if (path) {
        onFolderSelect(path);
      }
    } else {
      // Fallback for browser dev mode
      const path = prompt('请输入照片文件夹路径:');
      if (path) {
        onFolderSelect(path);
      }
    }
  };

  return (
    <AppBar position="static" elevation={0} sx={{ bgcolor: '#1E1E1E', borderBottom: '1px solid #333' }}>
      <MuiToolbar variant="dense">
        <Typography variant="h6" sx={{ flexGrow: 0, mr: 3, color: '#90caf9', fontWeight: 'bold' }}>
          📷 人像质量检测
        </Typography>

        <Button
          variant="outlined"
          size="small"
          startIcon={<FolderOpenIcon />}
          onClick={handleSelectFolder}
          sx={{ mr: 2, borderColor: '#555', color: '#e0e0e0' }}
        >
          选择文件夹
        </Button>

        {folderPath && (
          <Typography variant="body2" sx={{ flexGrow: 1, color: '#aaa', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {folderPath}
          </Typography>
        )}

        <Box sx={{ flexGrow: 1 }} />

        <Button
          variant="contained"
          size="small"
          startIcon={<FileDownloadIcon />}
          onClick={onExport}
          disabled={!folderPath}
          sx={{ mr: 2, bgcolor: '#4caf50', '&:hover': { bgcolor: '#388e3c' } }}
        >
          导出分类
        </Button>

        <Tooltip title={wsConnected ? '后端已连接' : '后端未连接'}>
          <IconButton size="small">
            {wsConnected ? (
              <WifiIcon sx={{ color: '#4caf50' }} />
            ) : (
              <WifiOffIcon sx={{ color: '#f44336' }} />
            )}
          </IconButton>
        </Tooltip>
      </MuiToolbar>
    </AppBar>
  );
}
