import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';

export default function StatusBar({ statusCounts, isProcessing, onStart, onCancel, folderPath }) {
  const { total, detected, pending } = statusCounts;
  const pct = total > 0 ? (detected / total) * 100 : 0;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
      {/* Progress bar */}
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

      {/* Action buttons */}
      <Button
        variant="contained"
        size="small"
        startIcon={<PlayArrowIcon />}
        onClick={onStart}
        disabled={!folderPath || isProcessing || pending === 0}
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
  );
}
