import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Tooltip,
  Box,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import { Close as CloseIcon, TrendingUp, TrendingDown } from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';
import type { Position } from '../api/client';

interface PositionsTableProps {
  positions: Position[];
  onClose?: (symbol1: string, symbol2: string) => void;
}

export default function PositionsTable({ positions, onClose }: PositionsTableProps) {
  const theme = useTheme();

  const getPositionIcon = (positionType: string) => {
    return positionType === 'LONG_SPREAD' ? (
      <TrendingUp sx={{ color: 'success.main', fontSize: 20 }} />
    ) : (
      <TrendingDown sx={{ color: 'error.main', fontSize: 20 }} />
    );
  };

  return (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Pair</TableCell>
            <TableCell align="center">Type</TableCell>
            <TableCell align="right">Entry Z-Score</TableCell>
            <TableCell align="right">Current Z-Score</TableCell>
            <TableCell align="right">Entry Prices</TableCell>
            <TableCell align="right">Current Prices</TableCell>
            <TableCell align="right">P&L</TableCell>
            <TableCell align="right">Duration</TableCell>
            <TableCell align="center">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {positions.length === 0 ? (
            <TableRow>
              <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  No open positions
                </Typography>
              </TableCell>
            </TableRow>
          ) : (
            positions.map((position) => (
              <TableRow
                key={position.pair_key}
                sx={{
                  '&:hover': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.05),
                  },
                }}
              >
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {getPositionIcon(position.position_type)}
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {position.symbol1}/{position.symbol2}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={position.position_type.replace('_', ' ')}
                    size="small"
                    color={position.position_type === 'LONG_SPREAD' ? 'success' : 'error'}
                    sx={{ fontSize: '0.65rem', height: 22 }}
                  />
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    sx={{ fontFamily: '"JetBrains Mono", monospace' }}
                  >
                    {position.entry_zscore.toFixed(4)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: '"JetBrains Mono", monospace',
                      color:
                        position.position_type === 'LONG_SPREAD'
                          ? position.current_zscore > position.entry_zscore
                            ? 'success.main'
                            : 'error.main'
                          : position.current_zscore < position.entry_zscore
                            ? 'success.main'
                            : 'error.main',
                      fontWeight: 600,
                    }}
                  >
                    {position.current_zscore.toFixed(4)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="caption" sx={{ display: 'block' }}>
                    {position.entry_price1?.toFixed(2) || '-'} /
                  </Typography>
                  <Typography variant="caption">
                    {position.entry_price2?.toFixed(2) || '-'}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="caption" sx={{ display: 'block' }}>
                    {position.current_price1?.toFixed(2) || '-'} /
                  </Typography>
                  <Typography variant="caption">
                    {position.current_price2?.toFixed(2) || '-'}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 600,
                      color:
                        (position.pnl_percent ?? 0) >= 0
                          ? 'success.main'
                          : 'error.main',
                    }}
                  >
                    {(position.pnl_percent ?? 0) >= 0 ? '+' : ''}
                    {(position.pnl_percent ?? 0).toFixed(2)}%
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {formatDistanceToNow(new Date(position.opened_at), {
                      locale: ru,
                    })}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Tooltip title="Close Position">
                    <IconButton
                      size="small"
                      onClick={() => onClose?.(position.symbol1, position.symbol2)}
                      sx={{ color: 'error.main' }}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

