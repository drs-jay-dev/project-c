import React from 'react';
import { Box, LinearProgress, Typography, Paper } from '@mui/material';

interface SyncProgressProps {
  progress?: {
    current: number;
    total: number;
    type: 'products' | 'customers' | 'orders';
  };
  status: 'success' | 'error' | 'in_progress';
  message: string;
}

const SyncProgress: React.FC<SyncProgressProps> = ({ progress, status, message }) => {
  const getProgressValue = () => {
    if (!progress) return 0;
    return (progress.current / progress.total) * 100;
  };

  const getProgressColor = () => {
    switch (status) {
      case 'success':
        return 'success';
      case 'error':
        return 'error';
      default:
        return 'primary';
    }
  };

  const getSyncTypeLabel = (type: string) => {
    switch (type) {
      case 'products':
        return 'Products';
      case 'customers':
        return 'Contacts';
      case 'orders':
        return 'Orders';
      default:
        return type;
    }
  };

  return (
    <Paper elevation={2} sx={{ p: 2, mb: 2 }}>
      <Box sx={{ width: '100%' }}>
        {progress && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="subtitle1" color="primary" sx={{ fontWeight: 'medium' }}>
              Syncing {getSyncTypeLabel(progress.type)}
            </Typography>
          </Box>
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Box sx={{ width: '100%', mr: 1 }}>
            <LinearProgress 
              variant="determinate" 
              value={getProgressValue()} 
              color={getProgressColor()}
              sx={{
                height: 10,
                borderRadius: 5,
                '& .MuiLinearProgress-bar': {
                  borderRadius: 5,
                },
              }}
            />
          </Box>
          <Box sx={{ minWidth: 45 }}>
            <Typography variant="body2" color="text.secondary">
              {`${Math.round(getProgressValue())}%`}
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {message}
          </Typography>
          {progress && (
            <Typography variant="body2" color="text.secondary">
              {`${progress.current} / ${progress.total} ${getSyncTypeLabel(progress.type)}`}
            </Typography>
          )}
        </Box>
      </Box>
    </Paper>
  );
};

export default SyncProgress;
