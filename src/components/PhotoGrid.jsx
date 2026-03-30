import React, { useRef, useState, useEffect, useMemo } from 'react';
import { Grid } from 'react-window';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import PhotoCard from './PhotoCard';

const CARD_WIDTH = 200;
const CARD_GAP = 8;

const CellRenderer = React.memo(function CellRenderer({
  columnIndex, rowIndex, style,
  photoNames, photoMapRef, selectedFileName, onSelectPhoto,
  columnCount, cardWidth, cardHeight,
}) {
  const index = rowIndex * columnCount + columnIndex;
  if (index >= photoNames.length) {
    return <div style={style} />;
  }
  const fileName = photoNames[index];
  const photo = photoMapRef.current.get(fileName);
  if (!photo) return <div style={style} />;
  const isSelected = selectedFileName === fileName;
  return (
    <div style={style}>
      <PhotoCard
        photo={photo}
        isSelected={isSelected}
        onSelect={onSelectPhoto}
        width={cardWidth - CARD_GAP}
        height={cardHeight}
      />
    </div>
  );
});

export default function PhotoGrid({ photoNames, photoMap, photoVersion, selectedFileName, onSelectPhoto }) {
  const containerRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const photoMapRef = useRef(photoMap);
  photoMapRef.current = photoMap;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const hasPhotos = photoNames.length > 0;
  const gridReady = hasPhotos && size.width > 0 && size.height > 0;

  const { columnCount, cardWidth, cardHeight, rowCount } = useMemo(() => {
    if (!gridReady) return { columnCount: 0, cardWidth: 0, cardHeight: 0, rowCount: 0 };
    const cc = Math.max(1, Math.floor((size.width + CARD_GAP) / (CARD_WIDTH + CARD_GAP)));
    const cw = (size.width - CARD_GAP * (cc - 1)) / cc;
    const ch = cw * (2 / 3);
    return { columnCount: cc, cardWidth: cw, cardHeight: ch, rowCount: Math.ceil(photoNames.length / cc) };
  }, [gridReady, size.width, size.height, photoNames.length]);

  // photoVersion is a number — Object.values({photoVersion: 5}) = [5],
  // so react-window's de() function correctly detects changes and refreshes cells.
  // photoMapRef is a stable ref object — CellRenderer reads from .current at render time.
  const cellProps = useMemo(() => ({
    photoNames,
    photoMapRef,
    selectedFileName,
    onSelectPhoto,
    columnCount,
    cardWidth,
    cardHeight,
    photoVersion,
  }), [photoNames, selectedFileName, onSelectPhoto, columnCount, cardWidth, cardHeight, photoVersion]);

  if (!hasPhotos) {
    return (
      <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
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
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      {gridReady && (
        <Grid
          key={photoVersion}
          columnCount={columnCount}
          columnWidth={cardWidth}
          rowCount={rowCount}
          rowHeight={cardHeight + CARD_GAP}
          width={size.width}
          height={size.height}
          overscanCount={3}
          cellComponent={CellRenderer}
          cellProps={cellProps}
        />
      )}
    </div>
  );
}
