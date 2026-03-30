// Status and quality label configuration
const statusConfig = {
  '未检测': { color: '#9e9e9e', icon: 'remove_circle_outline', label: '未检测' },
  '合格': { color: '#4caf50', icon: 'check_circle', label: '合格' },
  '需复核': { color: '#f44336', icon: 'error', label: '需复核' },
};

const qualityConfig = {
  '闭眼': { color: '#ff9800', bg: 'rgba(255, 152, 0, 0.2)', label: '闭眼' },
  '表情差': { color: '#e91e63', bg: 'rgba(233, 30, 99, 0.2)', label: '表情差' },
  '构图差': { color: '#9c27b0', bg: 'rgba(156, 39, 176, 0.2)', label: '构图差' },
  '欠曝': { color: '#2196f3', bg: 'rgba(33, 150, 243, 0.2)', label: '欠曝' },
  '过曝': { color: '#ffeb3b', bg: 'rgba(255, 235, 59, 0.2)', label: '过曝' },
  '合格': { color: '#4caf50', bg: 'rgba(76, 175, 80, 0.2)', label: '合格' },
};

export function getStatusConfig(status) {
  return statusConfig[status] || statusConfig['未检测'];
}

export function getQualityConfig(quality) {
  return qualityConfig[quality] || { color: '#9e9e9e', bg: 'rgba(158, 158, 158, 0.2)', label: quality };
}

export const STATUS_OPTIONS = ['未检测', '合格', '需复核'];

export const QUALITY_OPTIONS = ['闭眼', '表情差', '构图差', '欠曝', '过曝', '合格'];
