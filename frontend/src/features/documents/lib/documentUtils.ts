import React from 'react';
import {
  FileText,
  FileCode,
  Presentation,
  File,
} from 'lucide-react';

export function formatFileSize(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = bytes / Math.pow(1024, i);
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function getFileExtension(filename: string): string {
  const parts = filename.split('.');
  return parts.length > 1 ? parts.pop()?.toLowerCase() || '' : '';
}

export function getFileCategory(filename: string): 'pdf' | 'docx' | 'pptx' | 'txt' | 'other' {
  const ext = getFileExtension(filename);
  if (ext === 'pdf') return 'pdf';
  if (ext === 'docx' || ext === 'doc') return 'docx';
  if (ext === 'pptx' || ext === 'ppt') return 'pptx';
  if (ext === 'txt' || ext === 'md') return 'txt';
  return 'other';
}

export function getFileIcon(filename: string): React.ElementType {
  const cat = getFileCategory(filename);
  switch (cat) {
    case 'pdf':
      return FileText;
    case 'docx':
      return FileText;
    case 'pptx':
      return Presentation;
    case 'txt':
      return FileCode;
    default:
      return File;
  }
}

export function getFileBadgeStyle(filename: string): { bg: string; text: string; border: string; label: string } {
  const cat = getFileCategory(filename);
  switch (cat) {
    case 'pdf':
      return { bg: 'bg-rose-500/15', text: 'text-rose-400', border: 'border-rose-500/30', label: 'PDF' };
    case 'docx':
      return { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/30', label: 'DOCX' };
    case 'pptx':
      return { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30', label: 'PPTX' };
    case 'txt':
      return { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', label: 'TXT' };
    default:
      return { bg: 'bg-slate-500/15', text: 'text-slate-400', border: 'border-slate-500/30', label: 'FILE' };
  }
}
