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
  LinearProgress,
} from '@mui/material';
import {
  ShowChart as ChartIcon,
  PlayArrow as AnalyzeIcon,
  CheckCircle as CointegatedIcon,
  Cancel as NotCointegatedIcon,
} from '@mui/icons-material';
import type { PairMetrics } from '../api/client';

interface PairsTableProps {
  pairs: PairMetrics[];
  onAnalyze?: (symbol1: string, symbol2: string) => void;
  onViewChart?: (symbol1: string, symbol2: string) => void;
  isLoading?: boolean;
}

export default function PairsTable({ pairs, onAnalyze, onViewChart, isLoading }: PairsTableProps) {
  const theme = useTheme();

  const getZScoreColor = (zscore: number, upperThreshold = 2, lowerThreshold = -2) => {
    if (zscore >= upperThreshold) return theme.palette.error.main;
    if (zscore <= lowerThreshold) return theme.palette.success.main;
    if (Math.abs(zscore) >= 1.5) return theme.palette.warning.main;
    return theme.palette.text.primary;
  };

  const getZScoreLabel = (zscore: number, upperThreshold = 2, lowerThreshold = -2) => {
    if (zscore >= upperThreshold) return 'SHORT';
    if (zscore <= lowerThreshold) return 'LONG';
    return 'NEUTRAL';
  };

  return (
    <TableContainer component={Paper} sx={{ position: 'relative' }}>
      {isLoading && (
        <LinearProgress
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 1,
          }}
        />
      )}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Pair</TableCell>
            <TableCell align="center">Cointegrated</TableCell>
            <TableCell align="right">Correlation</TableCell>
            <TableCell align="right">Z-Score</TableCell>
            <TableCell align="right">Hedge Ratio</TableCell>
            <TableCell align="right">Half-Life</TableCell>
            <TableCell align="right">Hurst</TableCell>
            <TableCell align="center">Signal</TableCell>
            <TableCell align="center">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {pairs.length === 0 ? (
            <TableRow>
              <TableCell colSpan={9} align="center" sx={{ py: 4 }}>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  No pairs analyzed yet. Add a pair to get started.
                </Typography>
              </TableCell>
            </TableRow>
          ) : (
            pairs.map((pair) => (
              <TableRow
                key={`${pair.symbol1}-${pair.symbol2}`}
                sx={{
                  '&:hover': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.05),
                  },
                }}
              >
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {pair.symbol1}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      /
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {pair.symbol2}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell align="center">
                  <Tooltip title={`p-value: ${pair.cointegration_pvalue.toFixed(4)}`}>
                    <Box>
                      {pair.is_cointegrated ? (
                        <CointegatedIcon sx={{ color: 'success.main', fontSize: 20 }} />
                      ) : (
                        <NotCointegatedIcon sx={{ color: 'error.main', fontSize: 20 }} />
                      )}
                    </Box>
                  </Tooltip>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    sx={{
                      color: Math.abs(pair.correlation) >= 0.8 ? 'success.main' : 'text.primary',
                      fontWeight: Math.abs(pair.correlation) >= 0.8 ? 600 : 400,
                    }}
                  >
                    {(pair.correlation * 100).toFixed(1)}%
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    sx={{
                      color: getZScoreColor(pair.current_zscore),
                      fontWeight: 600,
                      fontFamily: '"JetBrains Mono", monospace',
                    }}
                  >
                    {pair.current_zscore.toFixed(4)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                    {pair.hedge_ratio.toFixed(4)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    sx={{
                      color: pair.half_life <= 20 ? 'success.main' : pair.half_life <= 40 ? 'warning.main' : 'error.main',
                    }}
                  >
                    {pair.half_life < 999 ? `${pair.half_life.toFixed(1)}d` : '∞'}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    sx={{
                      color: pair.hurst_exponent < 0.5 ? 'success.main' : 'error.main',
                    }}
                  >
                    {pair.hurst_exponent.toFixed(3)}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Chip
                    label={getZScoreLabel(pair.current_zscore)}
                    size="small"
                    color={
                      pair.current_zscore >= 2
                        ? 'error'
                        : pair.current_zscore <= -2
                          ? 'success'
                          : 'default'
                    }
                    sx={{
                      fontSize: '0.65rem',
                      height: 22,
                      fontWeight: 600,
                    }}
                  />
                </TableCell>
                <TableCell align="center">
                  <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                    <Tooltip title="Analyze">
                      <IconButton
                        size="small"
                        onClick={() => onAnalyze?.(pair.symbol1, pair.symbol2)}
                        sx={{ color: 'primary.main' }}
                      >
                        <AnalyzeIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="View Chart">
                      <IconButton
                        size="small"
                        onClick={() => onViewChart?.(pair.symbol1, pair.symbol2)}
                        sx={{ color: 'secondary.main' }}
                      >
                        <ChartIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

