import React, { useEffect, useState } from 'react';
import styled from 'styled-components';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Timeline as TimelineIcon,
  BarChart as BarChartIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  LineChart,
  Line,
} from 'recharts';
import { getOverview, getHourlyAnalytics } from '../services/api';

const PageHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
`;

const ChartsGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
`;

const ChartCard = styled.div`
  background: #ffffff;
  border-radius: 12px;
  padding: 22px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
`;

const TableCard = styled.div`
  background: #ffffff;
  border-radius: 12px;
  padding: 22px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
`;

const HeaderControls = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
`;

export default function AnalyticsPage() {
  const [overview, setOverview] = useState(null);
  const [hourlyRecords, setHourlyRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState(new Date());

  const loadData = async () => {
    try {
      const [ovData, hrData] = await Promise.all([
        getOverview(),
        getHourlyAnalytics(),
      ]);
      setOverview(ovData);
      setHourlyRecords(hrData);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error('Failed to load analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      loadData();
    }, 5000); // 5s auto-refresh
    return () => clearInterval(timer);
  }, [autoRefresh]);

  const { hourly_chart = [], form_distribution = [] } = overview || {};

  return (
    <div>
      <PageHeader>
        <div>
          <Typography variant="h5" sx={{ fontWeight: 700, color: '#0f172a' }}>
            Live Stream Analytics
          </Typography>
          <Typography variant="body2" sx={{ color: '#64748b' }}>
            Real-time hourly aggregations and form distribution from stream processing
          </Typography>
        </div>

        <HeaderControls>
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                sx={{
                  '& .MuiSwitch-switchBase.Mui-checked': {
                    color: '#288474',
                  },
                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                    backgroundColor: '#288474',
                  },
                }}
              />
            }
            label={
              <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
                {autoRefresh ? 'Auto-refreshing (5s)' : 'Auto-refresh paused'}
              </Typography>
            }
          />

          <Chip
            size="small"
            label={`Updated: ${lastRefreshed.toLocaleTimeString()}`}
            sx={{ backgroundColor: '#f1f5f9', color: '#64748b', fontSize: '12px' }}
          />

          <Tooltip title="Refresh now">
            <IconButton onClick={loadData} sx={{ color: '#288474' }}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </HeaderControls>
      </PageHeader>

      <ChartsGrid>
        <ChartCard>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <TimelineIcon sx={{ color: '#288474' }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a' }}>
              Hourly Submission Statistics
            </Typography>
          </Box>
          <Box sx={{ width: '100%', height: 280 }}>
            {hourly_chart.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={hourly_chart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="hour"
                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                    tickFormatter={(val) => val.split(' ')[1] || val}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
                  <ChartTooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: 8,
                      border: 'none',
                      color: '#ffffff',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#288474"
                    strokeWidth={3}
                    dot={{ r: 4, fill: '#288474' }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                No hourly activity recorded yet
              </Box>
            )}
          </Box>
        </ChartCard>

        <ChartCard>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <BarChartIcon sx={{ color: '#288474' }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a' }}>
              Form-Wise Submission Counts
            </Typography>
          </Box>
          <Box sx={{ width: '100%', height: 280 }}>
            {form_distribution.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={form_distribution} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="form_id" tick={{ fontSize: 11, fill: '#475569' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
                  <ChartTooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: 8,
                      border: 'none',
                      color: '#ffffff',
                    }}
                  />
                  <Bar dataKey="count" fill="#288474" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                No form counts recorded yet
              </Box>
            )}
          </Box>
        </ChartCard>
      </ChartsGrid>

      <TableCard>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <StorageIcon sx={{ color: '#288474' }} />
          <div>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a' }}>
              Flink Hourly Aggregations Database Table
            </Typography>
            <Typography variant="caption" sx={{ color: '#64748b' }}>
              Records aggregated per form_id and hour bucket in the database
            </Typography>
          </div>
        </Box>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ '& th': { color: '#64748b', fontWeight: 600, borderBottom: '1px solid #f1f5f9' } }}>
                <TableCell>Record ID</TableCell>
                <TableCell>Form ID</TableCell>
                <TableCell>Hour Bucket (UTC)</TableCell>
                <TableCell align="right">Submission Count</TableCell>
                <TableCell align="right">Last Aggregated</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading && hourlyRecords.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                    <CircularProgress sx={{ color: '#288474' }} size={28} />
                  </TableCell>
                </TableRow>
              ) : hourlyRecords.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 4, color: '#94a3b8' }}>
                    No persisted Flink hourly buckets yet. Start the Flink job or run submissions to trigger aggregation.
                  </TableCell>
                </TableRow>
              ) : (
                hourlyRecords.map((rec) => (
                  <TableRow key={rec.id} hover sx={{ '& td': { borderBottom: '1px solid #f8fafc' } }}>
                    <TableCell sx={{ fontWeight: 600 }}>#{rec.id}</TableCell>
                    <TableCell>
                      <Chip
                        label={rec.form_id}
                        size="small"
                        sx={{ backgroundColor: '#eef7f5', color: '#288474', fontWeight: 600 }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '13px' }}>
                      {new Date(rec.hour_bucket).toUTCString()}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: '#0f172a' }}>
                      {rec.count.toLocaleString()}
                    </TableCell>
                    <TableCell align="right" sx={{ fontSize: '12px', color: '#64748b' }}>
                      {new Date(rec.last_updated).toLocaleTimeString()}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </TableCard>
    </div>
  );
}
