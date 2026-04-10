import { useState, useCallback, useRef, useMemo } from 'react';

export default function usePhotoStore() {
  const [photoNames, setPhotoNames] = useState([]);
  const [photoMap, setPhotoMap] = useState(() => new Map());
  const [photoVersion, setPhotoVersion] = useState(0);
  const [selectedFileName, setSelectedFileName] = useState(null);

  const photoMapRef = useRef(photoMap);
  photoMapRef.current = photoMap;

  const selectedPhoto = selectedFileName ? photoMap.get(selectedFileName) : null;

  const loadPhotos = useCallback((photoList) => {
    const names = photoList.map((p) => p.photo_metadata.file_info.file_name);
    const map = new Map();
    photoList.forEach((p) => map.set(p.photo_metadata.file_info.file_name, p));
    setPhotoNames(names);
    setPhotoMap(() => map);
    setPhotoVersion(0);
    setSelectedFileName(null);
  }, []);

  const updatePhoto = useCallback((fileName, photoData) => {
    setPhotoMap((prev) => {
      const next = new Map(prev);
      next.set(fileName, photoData);
      return next;
    });
    setPhotoVersion((v) => v + 1);
  }, []);

  const patchPhoto = useCallback((fileName, updates) => {
    setPhotoMap((prev) => {
      const next = new Map(prev);
      const photo = next.get(fileName);
      if (photo) {
        next.set(fileName, {
          ...photo,
          photo_metadata: { ...photo.photo_metadata, ...updates },
        });
      }
      return next;
    });
    setPhotoVersion((v) => v + 1);
  }, []);

  const selectPhoto = useCallback((photo) => {
    setSelectedFileName(photo?.photo_metadata?.file_info?.file_name || null);
  }, []);

  const getFilteredNames = useCallback((filterTags) => {
    if (!filterTags || filterTags.size === 0) return photoNames;
    return photoNames.filter((name) => {
      const photo = photoMap.get(name);
      if (!photo) return false;
      const qualities = photo.photo_metadata?.quality || [];
      return qualities.some((q) => filterTags.has(q));
    });
  }, [photoNames, photoMap]);

  const getStatusCounts = useCallback((filteredLength) => {
    let detected = 0;
    for (const p of photoMap.values()) {
      if (p.photo_metadata?.status !== '未检测') detected++;
    }
    return { total: filteredLength, detected, pending: filteredLength - detected };
  }, [photoMap, photoVersion]);

  return {
    photoNames,
    photoMap,
    photoVersion,
    selectedPhoto,
    selectedFileName,
    photoMapRef,
    loadPhotos,
    updatePhoto,
    patchPhoto,
    selectPhoto,
    getFilteredNames,
    getStatusCounts,
  };
}
