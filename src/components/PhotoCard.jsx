import React from 'react';
import Box from '@mui/material/Box';
import { getStatusConfig, getQualityConfig } from '../utils/statusConfig';

function buildThumbUrl(filePath) {
  if (!filePath) return '';
  // filePath: "D:\photos\IMG001.JPG" → "file:///D:/photos/.thumbnails/IMG001.JPG"
  const normalized = filePath.replace(/\\/g, '/');
  const lastSlash = normalized.lastIndexOf('/');
  const dir = normalized.substring(0, lastSlash);
  const file = normalized.substring(lastSlash + 1);
  return `file:///${dir}/.thumbnails/${file}`;
}

const PhotoCard = React.memo(function PhotoCard({ photo, isSelected, onSelect, width, height }) {
  const meta = photo?.photo_metadata;
  if (!meta) return null;

  const fileInfo = meta.file_info;
  const status = meta.status || '未检测';
  const qualities = meta.quality || [];
  const statusConf = getStatusConfig(status);

  const thumbUrl = buildThumbUrl(fileInfo.file_path);

  return (
    <Box
      onClick={() => onSelect(photo)}
      sx={{
        position: 'relative',
        borderRadius: '8px',
        overflow: 'hidden',
        cursor: 'pointer',
        border: isSelected ? '2px solid #90caf9' : '2px solid transparent',
        bgcolor: '#2a2a2a',
        width: width || '100%',
        height: height || '100%',
      }}
    >
      <img
        src={thumbUrl}
        alt={fileInfo.file_name}
        loading="lazy"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
        }}
      />

      {/* Status badge - top left */}
      <Box
        sx={{
          position: 'absolute',
          top: 6,
          left: 6,
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          bgcolor: 'rgba(0,0,0,0.7)',
          borderRadius: '12px',
          px: 1,
          py: 0.3,
        }}
      >
        <Box
          sx={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: statusConf.color,
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: '11px', color: statusConf.color, fontWeight: 500 }}>
          {statusConf.label}
        </span>
      </Box>

      {/* Quality tags - bottom */}
      {qualities.length > 0 && status !== '未检测' && (
        <Box
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            display: 'flex',
            flexWrap: 'wrap',
            gap: 0.5,
            p: 0.5,
            bgcolor: 'linear-gradient(transparent, rgba(0,0,0,0.8))',
          }}
        >
          {qualities.map((q, i) => {
            const qConf = getQualityConfig(q);
            return (
              <span
                key={i}
                style={{
                  fontSize: '10px',
                  color: qConf.color,
                  backgroundColor: qConf.bg,
                  padding: '1px 6px',
                  borderRadius: '4px',
                  fontWeight: 500,
                }}
              >
                {qConf.label}
              </span>
            );
          })}
        </Box>
      )}
    </Box>
  );
});

export default PhotoCard;
