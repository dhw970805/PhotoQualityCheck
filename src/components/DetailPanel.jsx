import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Divider from '@mui/material/Divider';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import LinearProgress from '@mui/material/LinearProgress';
import { getStatusConfig, getQualityConfig, STATUS_OPTIONS, QUALITY_OPTIONS } from '../utils/statusConfig';
import { getThumbUrl } from '../services/api';

function ScoreBar({ label, value }) {
  const color =
    value >= 70 ? '#4caf50' :
    value >= 50 ? '#ff9800' :
    '#f44336';

  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
        <Typography variant="body2" sx={{ color: '#aaa' }}>{label}</Typography>
        <Typography variant="body2" sx={{ color, fontWeight: 'bold' }}>{value}</Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={value}
        sx={{
          height: 6,
          borderRadius: 3,
          bgcolor: '#333',
          '& .MuiLinearProgress-bar': {
            bgcolor: color,
            borderRadius: 3,
          },
        }}
      />
    </Box>
  );
}

export default function DetailPanel({ photo, onUpdateResult, onRetry, isProcessing }) {
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});

  if (!photo) {
    return (
      <Box sx={{ p: 3, color: '#666', textAlign: 'center', mt: 8 }}>
        <Typography variant="body1">点击左侧照片查看详情</Typography>
      </Box>
    );
  }

  const meta = photo.photo_metadata;
  const fileInfo = meta.file_info;
  const scores = meta.scores || {};
  const status = meta.status || '未检测';
  const qualities = meta.quality || [];
  const statusConf = getStatusConfig(status);

  const handleStartEdit = () => {
    setEditData({
      status: status,
      quality: [...qualities],
      advise: meta.advise || '',
      reason: meta.reason || '',
      scores: { ...scores },
    });
    setEditing(true);
  };

  const handleSave = () => {
    onUpdateResult(fileInfo.file_name, editData);
    setEditing(false);
  };

  const handleCancelEdit = () => {
    setEditing(false);
  };

  const imgUrl = getThumbUrl(fileInfo.file_path);

  return (
    <Box sx={{ p: 2 }}>
      {/* Photo preview */}
      {imgUrl && (
        <Box
          component="img"
          src={imgUrl}
          alt={fileInfo.file_name}
          sx={{
            width: '100%',
            maxHeight: 200,
            objectFit: 'contain',
            borderRadius: '8px',
            bgcolor: '#000',
            mb: 2,
          }}
        />
      )}

      {/* File name */}
      <Typography variant="subtitle2" sx={{ color: '#90caf9', mb: 0.5, wordBreak: 'break-all' }}>
        {fileInfo.file_name}
      </Typography>

      <Divider sx={{ my: 1.5, borderColor: '#333' }} />

      {/* Status */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" sx={{ color: '#888', mb: 0.5, display: 'block' }}>状态</Typography>
        {editing ? (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {STATUS_OPTIONS.map((s) => {
              const conf = getStatusConfig(s);
              return (
                <Chip
                  key={s}
                  label={s}
                  size="small"
                  onClick={() => setEditData((d) => ({ ...d, status: s }))}
                  sx={{
                    bgcolor: editData.status === s ? conf.color : 'transparent',
                    color: editData.status === s ? '#000' : conf.color,
                    border: `1px solid ${conf.color}`,
                  }}
                />
              );
            })}
          </Box>
        ) : (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: statusConf.color }} />
            <Typography variant="body1" sx={{ color: statusConf.color, fontWeight: 500 }}>
              {statusConf.label}
            </Typography>
          </Box>
        )}
      </Box>

      {/* Quality tags */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" sx={{ color: '#888', mb: 0.5, display: 'block' }}>质量问题</Typography>
        {editing ? (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {QUALITY_OPTIONS.map((q) => {
              const conf = getQualityConfig(q);
              const selected = editData.quality.includes(q);
              return (
                <Chip
                  key={q}
                  label={q}
                  size="small"
                  onClick={() => {
                    setEditData((d) => ({
                      ...d,
                      quality: selected
                        ? d.quality.filter((x) => x !== q)
                        : [...d.quality, q],
                    }));
                  }}
                  sx={{
                    bgcolor: selected ? conf.bg : 'transparent',
                    color: conf.color,
                    border: `1px solid ${conf.color}`,
                  }}
                />
              );
            })}
          </Box>
        ) : (
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {qualities.length === 0 ? (
              <Typography variant="body2" sx={{ color: '#666' }}>无</Typography>
            ) : (
              qualities.map((q, i) => {
                const conf = getQualityConfig(q);
                return (
                  <Chip
                    key={i}
                    label={conf.label}
                    size="small"
                    sx={{ bgcolor: conf.bg, color: conf.color }}
                  />
                );
              })
            )}
          </Box>
        )}
      </Box>

      <Divider sx={{ my: 1.5, borderColor: '#333' }} />

      {/* Scores */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" sx={{ color: '#888', mb: 1, display: 'block' }}>评分</Typography>
        {editing ? (
          <Box>
            {['expression', 'composition', 'exposure'].map((key) => {
              const labels = { expression: '表情', composition: '构图', exposure: '曝光' };
              return (
                <Box key={key} sx={{ mb: 1 }}>
                  <Typography variant="body2" sx={{ color: '#aaa', mb: 0.3 }}>{labels[key]}</Typography>
                  <TextField
                    type="number"
                    size="small"
                    variant="outlined"
                    value={editData.scores[key] || 0}
                    onChange={(e) =>
                      setEditData((d) => ({
                        ...d,
                        scores: { ...d.scores, [key]: Math.max(0, Math.min(100, parseInt(e.target.value) || 0)) },
                      }))
                    }
                    inputProps={{ min: 0, max: 100, style: { color: '#e0e0e0' } }}
                    sx={{ width: 80 }}
                  />
                </Box>
              );
            })}
          </Box>
        ) : (
          <Box>
            <ScoreBar label="表情" value={scores.expression || 0} />
            <ScoreBar label="构图" value={scores.composition || 0} />
            <ScoreBar label="曝光" value={scores.exposure || 0} />
          </Box>
        )}
      </Box>

      <Divider sx={{ my: 1.5, borderColor: '#333' }} />

      {/* Reason & Advise */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" sx={{ color: '#888', mb: 0.5, display: 'block' }}>分析原因</Typography>
        {editing ? (
          <TextField
            fullWidth
            multiline
            minRows={2}
            size="small"
            value={editData.reason || ''}
            onChange={(e) => setEditData((d) => ({ ...d, reason: e.target.value }))}
            inputProps={{ style: { color: '#e0e0e0' } }}
          />
        ) : (
          <Typography variant="body2" sx={{ color: '#ccc' }}>
            {meta.reason || '无'}
          </Typography>
        )}
      </Box>

      <Box sx={{ mb: 2 }}>
        <Typography variant="caption" sx={{ color: '#888', mb: 0.5, display: 'block' }}>建议</Typography>
        {editing ? (
          <TextField
            fullWidth
            multiline
            minRows={2}
            size="small"
            value={editData.advise || ''}
            onChange={(e) => setEditData((d) => ({ ...d, advise: e.target.value }))}
            inputProps={{ style: { color: '#e0e0e0' } }}
          />
        ) : (
          <Typography variant="body2" sx={{ color: '#ccc' }}>
            {meta.advise || '无'}
          </Typography>
        )}
      </Box>

      {/* Actions */}
      <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
        {editing ? (
          <>
            <Button
              variant="contained"
              size="small"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              sx={{ flex: 1, bgcolor: '#4caf50' }}
            >
              保存
            </Button>
            <Button
              variant="outlined"
              size="small"
              onClick={handleCancelEdit}
              sx={{ flex: 1, borderColor: '#555', color: '#e0e0e0' }}
            >
              取消
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="outlined"
              size="small"
              onClick={handleStartEdit}
              sx={{ flex: 1, borderColor: '#555', color: '#e0e0e0' }}
            >
              编辑
            </Button>
            <Tooltip title="重新检测该照片">
              <IconButton
                size="small"
                onClick={() => onRetry(fileInfo.file_name)}
                disabled={isProcessing}
                sx={{ color: '#90caf9' }}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </>
        )}
      </Box>
    </Box>
  );
}
