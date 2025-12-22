import {
  Paper,
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
  Divider,
  alpha,
  useTheme,
} from '@mui/material';
import {
  TrendingUp as LongIcon,
  TrendingDown as ShortIcon,
  ExitToApp as ExitIcon,
  Warning as StopLossIcon,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';
import type { Signal } from '../api/client';

interface SignalsListProps {
  signals: Signal[];
  maxHeight?: number;
}

export default function SignalsList({ signals, maxHeight = 400 }: SignalsListProps) {
  const theme = useTheme();

  const getSignalIcon = (signalType: string) => {
    switch (signalType) {
      case 'LONG_SPREAD':
        return <LongIcon sx={{ color: 'success.main' }} />;
      case 'SHORT_SPREAD':
        return <ShortIcon sx={{ color: 'error.main' }} />;
      case 'EXIT_LONG':
      case 'EXIT_SHORT':
        return <ExitIcon sx={{ color: 'warning.main' }} />;
      case 'STOP_LOSS':
        return <StopLossIcon sx={{ color: 'error.main' }} />;
      default:
        return null;
    }
  };

  const getSignalColor = (signalType: string): 'success' | 'error' | 'warning' | 'default' => {
    switch (signalType) {
      case 'LONG_SPREAD':
        return 'success';
      case 'SHORT_SPREAD':
        return 'error';
      case 'EXIT_LONG':
      case 'EXIT_SHORT':
        return 'warning';
      case 'STOP_LOSS':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatSignalType = (signalType: string) => {
    return signalType.replace('_', ' ');
  };

  return (
    <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}` }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Recent Signals
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          Last {signals.length} trading signals
        </Typography>
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto', maxHeight }}>
        {signals.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              No signals generated yet
            </Typography>
          </Box>
        ) : (
          <List disablePadding>
            {signals.map((signal, index) => (
              <Box key={`${signal.symbol1}-${signal.symbol2}-${signal.timestamp}`}>
                <ListItem
                  sx={{
                    py: 1.5,
                    px: 2,
                    '&:hover': {
                      backgroundColor: alpha(theme.palette.primary.main, 0.04),
                    },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 40 }}>
                    {getSignalIcon(signal.signal_type)}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {signal.symbol1}/{signal.symbol2}
                        </Typography>
                        <Chip
                          label={formatSignalType(signal.signal_type)}
                          size="small"
                          color={getSignalColor(signal.signal_type)}
                          sx={{ height: 20, fontSize: '0.65rem' }}
                        />
                        <Chip
                          label={signal.strength}
                          size="small"
                          variant="outlined"
                          sx={{
                            height: 18,
                            fontSize: '0.6rem',
                            borderColor: alpha(theme.palette.text.secondary, 0.3),
                          }}
                        />
                      </Box>
                    }
                    secondary={
                      <Box sx={{ mt: 0.5 }}>
                        <Typography
                          variant="caption"
                          sx={{
                            color: 'text.secondary',
                            display: 'flex',
                            gap: 2,
                            flexWrap: 'wrap',
                          }}
                        >
                          <span>Z-Score: {signal.zscore.toFixed(4)}</span>
                          <span>Confidence: {(signal.confidence * 100).toFixed(0)}%</span>
                          <span>
                            {formatDistanceToNow(new Date(signal.timestamp), {
                              addSuffix: true,
                              locale: ru,
                            })}
                          </span>
                        </Typography>
                        {signal.entry_price1 && signal.entry_price2 && (
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            Entry: {signal.entry_price1.toFixed(2)} / {signal.entry_price2.toFixed(2)}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                </ListItem>
                {index < signals.length - 1 && <Divider sx={{ opacity: 0.1 }} />}
              </Box>
            ))}
          </List>
        )}
      </Box>
    </Paper>
  );
}

