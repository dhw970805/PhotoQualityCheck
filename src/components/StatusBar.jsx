import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';

export default function StatusBar({ statusCounts, isProcessing, onStart, onCancel, folderPath, importProgress }) {
  const { total, detected, pending } = statusCounts;
  const pct = total > 0 ? (detected / total) * 100 : 0;
  const isImporting = importProgress.total > 0 && importProgress.current < importProgress.total;
  const importPct = importProgress.total > 0 ? (importProgress.current / importProgress.total) * 100 : 0;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      {/* Import progress bar */}
      {isImporting && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FolderOpenIcon sx={{ fontSize: 16, color: '#ffab40' }} />
          <Typography variant="body2" sx={{ color: '#ffab40', minWidth: 90 }}>
            导入图片: {importProgress.current}/{importProgress.total}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={importPct}
            sx={{
              flexGrow: 1,
              height: 4,
              borderRadius: 2,
              bgcolor: '#333',
              '& .MuiLinearProgress-bar': {
                bgcolor: '#ffab40',
                borderRadius: 2,
              },
            }}
          />
        </Box>
      )}

      {/* Detection progress bar and action buttons */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
        <Box sx={{ flexGrow: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
            <Typography variant="body2" sx={{ color: '#aaa' }}>
              进度: {detected}/{total}
            </Typography>
            <Typography variant="body2" sx={{ color: '#aaa' }}>
              待检测: {pending}
            </Typography>
          </Box>
          <LinearProgress
            variant={isProcessing ? 'indeterminate' : 'determinate'}
            value={pct}
            sx={{
              height: 6,
              borderRadius: 3,
              bgcolor: '#333',
              '& .MuiLinearProgress-bar': {
                bgcolor: isProcessing ? '#90caf9' : '#4caf50',
                borderRadius: 3,
              },
            }}
          />
        </Box>

        <Button
          variant="contained"
          size="small"
          startIcon={<PlayArrowIcon />}
          onClick={onStart}
          disabled={!folderPath || isProcessing || pending === 0 || isImporting}
          sx={{ minWidth: 100, bgcolor: '#1976d2', '&:hover': { bgcolor: '#1565c0' } }}
        >
          开始检测
        </Button>

        {isProcessing && (
          <Button
            variant="outlined"
            size="small"
            startIcon={<StopIcon />}
            onClick={onCancel}
            sx={{ minWidth: 80, borderColor: '#f44336', color: '#f44336' }}
          >
            取消
          </Button>
        )}
      </Box>
    </Box>
  );
}
