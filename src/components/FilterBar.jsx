import React from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { QUALITY_OPTIONS, getQualityConfig } from '../utils/statusConfig';

const ALL_TAG = '全部';

export default function FilterBar({ filterTags, onFilterChange }) {
  const tags = [ALL_TAG, ...QUALITY_OPTIONS];

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        px: 2,
        py: 1,
        borderBottom: '1px solid #333',
        bgcolor: '#1E1E1E',
        flexShrink: 0,
      }}
    >
      <Typography variant="body2" sx={{ color: '#888', mr: 0.5, whiteSpace: 'nowrap' }}>
        筛选:
      </Typography>
      {tags.map((tag) => {
        const isAll = tag === ALL_TAG;
        const isActive = isAll ? filterTags.size === 0 : filterTags.has(tag);
        const conf = isAll ? null : getQualityConfig(tag);
        return (
          <Chip
            key={tag}
            label={tag}
            size="small"
            onClick={() => {
              if (isAll) {
                onFilterChange(new Set());
              } else {
                onFilterChange((prev) => {
                  const next = new Set(prev);
                  if (next.has(tag)) {
                    next.delete(tag);
                  } else {
                    next.add(tag);
                  }
                  return next;
                });
              }
            }}
            sx={{
              bgcolor: isActive
                ? (isAll ? '#555' : conf.bg)
                : 'transparent',
              color: isActive
                ? (isAll ? '#e0e0e0' : conf.color)
                : '#888',
              border: isActive
                ? (isAll ? '1px solid #777' : `1px solid ${conf.color}`)
                : '1px solid #555',
              '&:hover': {
                bgcolor: isActive
                  ? (isAll ? '#666' : conf.bg)
                  : 'rgba(255,255,255,0.05)',
              },
            }}
          />
        );
      })}
    </Box>
  );
}
