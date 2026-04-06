import React, { useRef, useState, useEffect, useMemo, useCallback } from 'react';
import { Grid, useGridRef } from 'react-window';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import PhotoCard from './PhotoCard';

const CARD_WIDTH = 200;
const CARD_GAP = 8;

// photoVersion is passed in cellProps to bust React.memo + react-window cache.
// It's not destructured here but present in props for shallow comparison.
const CellRenderer = React.memo(function CellRenderer(props) {
  const { columnIndex, rowIndex, style, photoNames, photoMapRef,
    selectedFileName, onSelectPhoto, columnCount, cardWidth, cardHeight } = props;
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

export default function PhotoGrid({ photoNames, photoMap, photoVersion, selectedFileName, onSelectPhoto, onUpdateResult }) {
  const containerRef = useRef(null);
  const gridRef = useGridRef();
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

  // Keyboard navigation: arrow keys to move selection, space to toggle 合格/需复核
  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = e.target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) return;
      if (!photoNames.length || columnCount <= 0) return;

      const currentIndex = selectedFileName ? photoNames.indexOf(selectedFileName) : -1;

      let newIndex = -1;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        newIndex = currentIndex < 0 ? 0 : Math.min(currentIndex + columnCount, photoNames.length - 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        newIndex = currentIndex < 0 ? 0 : Math.max(currentIndex - columnCount, 0);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        newIndex = currentIndex < 0 ? 0 : Math.min(currentIndex + 1, photoNames.length - 1);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        newIndex = currentIndex < 0 ? 0 : Math.max(currentIndex - 1, 0);
      } else if (e.key === ' ') {
        e.preventDefault();
        if (currentIndex < 0 || !onUpdateResult) return;
        const photo = photoMapRef.current.get(photoNames[currentIndex]);
        if (!photo) return;
        const meta = photo.photo_metadata;
        const currentStatus = meta.status || '未检测';
        const newStatus = currentStatus === '合格' ? '需复核' : '合格';
        let newQuality = [...(meta.quality || [])];
        if (newStatus === '合格') {
          if (!newQuality.includes('合格')) newQuality.push('合格');
        } else {
          newQuality = newQuality.filter(q => q !== '合格');
        }
        onUpdateResult(meta.file_info.file_name, { status: newStatus, quality: newQuality });
        return;
      } else {
        return;
      }

      if (newIndex >= 0) {
        const photo = photoMapRef.current.get(photoNames[newIndex]);
        if (photo) {
          onSelectPhoto(photo);
          const rowIndex = Math.floor(newIndex / columnCount);
          const colIndex = newIndex % columnCount;
          gridRef.current?.scrollToCell?.({ rowIndex, columnIndex: colIndex });
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [photoNames, selectedFileName, columnCount, onSelectPhoto, onUpdateResult]);

  // photoVersion in cellProps triggers react-window's internal useMemo refresh.
  // photoMapRef is stable — CellRenderer reads .current at render time.
  // No key= on Grid — avoids full remount on every photo update.
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
          gridRef={gridRef}
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
