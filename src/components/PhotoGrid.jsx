import React, { useRef, useState, useEffect } from 'react';
import { Grid } from 'react-window';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import PhotoCard from './PhotoCard';

const CARD_WIDTH = 200;
const CARD_GAP = 8;

function CellRenderer({ columnIndex, rowIndex, style, photos, selectedPhoto, onSelectPhoto, columnCount, cardWidth, cardHeight }) {
  const index = rowIndex * columnCount + columnIndex;
  if (index >= photos.length) {
    return <div style={style} />;
  }
  const photo = photos[index];
  return (
    <div style={style}>
      <PhotoCard
        photo={photo}
        isSelected={selectedPhoto}
        onSelect={onSelectPhoto}
        width={cardWidth - CARD_GAP}
        height={cardHeight}
      />
    </div>
  );
}

export default function PhotoGrid({ photos, selectedPhoto, onSelectPhoto }) {
  const containerRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [photos.length > 0]);

  const hasPhotos = photos && photos.length > 0;
  const gridReady = hasPhotos && size.width > 0 && size.height > 0;

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      {!hasPhotos ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#666',
          }}
        >
          <Typography variant="h6" sx={{ mb: 1 }}>
            请先选择包含照片的文件夹
          </Typography>
          <Typography variant="body2">
            点击上方"选择文件夹"按钮开始
          </Typography>
        </Box>
      ) : gridReady ? (() => {
        const columnCount = Math.max(1, Math.floor((size.width + CARD_GAP) / (CARD_WIDTH + CARD_GAP)));
        const cardWidth = (size.width - CARD_GAP * (columnCount - 1)) / columnCount;
        const cardHeight = cardWidth * (2 / 3);
        const rowCount = Math.ceil(photos.length / columnCount);

        return (
          <Grid
            columnCount={columnCount}
            columnWidth={cardWidth}
            rowCount={rowCount}
            rowHeight={cardHeight + CARD_GAP}
            width={size.width}
            height={size.height}
            overscanCount={3}
            cellComponent={CellRenderer}
            cellProps={{ photos, selectedPhoto, onSelectPhoto, columnCount, cardWidth, cardHeight }}
          />
        );
      })() : null}
    </div>
  );
}
