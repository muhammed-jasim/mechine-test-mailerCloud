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
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  Description as DescriptionIcon,
  Today as TodayIcon,
  Visibility as VisibilityIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
} from 'recharts';
import { getOverview } from '../services/api';
import DetailModal from '../components/DetailModal';

const PageHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
`;

const StatsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 28px;
`;

const StatCard = styled.div`
  background: #ffffff;
  border-radius: 12px;
  padding: 22px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03);
  border: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  gap: 18px;
`;

const IconWrapper = styled.div`
  width: 50px;
  height: 50px;
  border-radius: 10px;
  background-color: ${(props) => props.bg || '#eef7f5'};
  color: ${(props) => props.color || '#288474'};
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    font-size: 26px;
  }
`;

const ChartsRow = styled.div`
  display: grid;
  grid-template-columns: 2fr 1.2fr;
  gap: 20px;
  margin-bottom: 28px;

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

export default function Overview({ onSelectForm }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedSubmission, setSelectedSubmission] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await getOverview();
      setData(res);
    } catch (err) {
      console.error('Failed to load overview:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // 10s auto-refresh
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <CircularProgress sx={{ color: '#288474' }} />
      </Box>
    );
  }

  const {
    total_submissions = 0,
    total_forms = 0,
    today_submissions = 0,
    hourly_chart = [],
    form_distribution = [],
    recent_submissions = [],
  } = data || {};

  return (
    <div>
      <PageHeader>
        <div>
          <Typography variant="h5" sx={{ fontWeight: 700, color: '#0f172a' }}>
            System Overview
          </Typography>
          <Typography variant="body2" sx={{ color: '#64748b' }}>
            Real-time form submissions and event processing metrics
          </Typography>
        </div>
        <Tooltip title="Refresh now">
          <IconButton onClick={fetchData} sx={{ color: '#288474' }}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </PageHeader>

      <StatsGrid>
        <StatCard>
          <IconWrapper bg="#eef7f5" color="#288474">
            <TrendingUpIcon />
          </IconWrapper>
          <div>
            <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
              TOTAL SUBMISSIONS
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a', mt: 0.5 }}>
              {total_submissions.toLocaleString()}
            </Typography>
          </div>
        </StatCard>

        <StatCard>
          <IconWrapper bg="#eff6ff" color="#3b82f6">
            <DescriptionIcon />
          </IconWrapper>
          <div>
            <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
              TOTAL ACTIVE FORMS
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a', mt: 0.5 }}>
              {total_forms}
            </Typography>
          </div>
        </StatCard>

        <StatCard>
          <IconWrapper bg="#f0fdf4" color="#16a34a">
            <TodayIcon />
          </IconWrapper>
          <div>
            <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
              TODAY'S SUBMISSIONS
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: '#0f172a', mt: 0.5 }}>
              {today_submissions.toLocaleString()}
            </Typography>
          </div>
        </StatCard>
      </StatsGrid>

      <ChartsRow>
        <ChartCard>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a', mb: 2 }}>
            Hourly Submissions (Recent 24 Hours)
          </Typography>
          <Box sx={{ width: '100%', height: 260 }}>
            {hourly_chart.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={hourly_chart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#288474" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#288474" stopOpacity={0} />
                    </linearGradient>
                  </defs>
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
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#288474"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#colorCount)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                No hourly activity recorded yet
              </Box>
            )}
          </Box>
        </ChartCard>

        <ChartCard>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a', mb: 2 }}>
            Submissions by Form
          </Typography>
          <Box sx={{ width: '100%', height: 260 }}>
            {form_distribution.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={form_distribution} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} allowDecimals={false} />
                  <YAxis
                    dataKey="form_id"
                    type="category"
                    tick={{ fontSize: 11, fill: '#475569' }}
                    width={80}
                  />
                  <ChartTooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: 8,
                      border: 'none',
                      color: '#ffffff',
                    }}
                  />
                  <Bar dataKey="count" fill="#288474" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                No forms submitted yet
              </Box>
            )}
          </Box>
        </ChartCard>
      </ChartsRow>

      <TableCard>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, color: '#0f172a', mb: 2 }}>
          Recent Submissions
        </Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ '& th': { color: '#64748b', fontWeight: 600, borderBottom: '1px solid #f1f5f9' } }}>
                <TableCell>ID</TableCell>
                <TableCell>Form ID</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Idempotency Key</TableCell>
                <TableCell>Timestamp (UTC)</TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {recent_submissions.length > 0 ? (
                recent_submissions.map((sub) => (
                  <TableRow key={sub.id} hover sx={{ '& td': { borderBottom: '1px solid #f8fafc' } }}>
                    <TableCell sx={{ fontWeight: 600 }}>#{sub.id}</TableCell>
                    <TableCell>
                      <Chip
                        label={sub.form_id}
                        size="small"
                        clickable
                        onClick={() => onSelectForm && onSelectForm(sub.form_id)}
                        sx={{
                          backgroundColor: '#eef7f5',
                          color: '#288474',
                          fontWeight: 600,
                          fontSize: '12px',
                        }}
                      />
                    </TableCell>
                    <TableCell>{sub.email}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '12px', color: '#64748b' }}>
                      {sub.idempotency_key}
                    </TableCell>
                    <TableCell sx={{ fontSize: '13px', color: '#64748b' }}>
                      {new Date(sub.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="View JSON Details">
                        <IconButton
                          size="small"
                          onClick={() => setSelectedSubmission(sub)}
                          sx={{ color: '#288474' }}
                        >
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 4, color: '#94a3b8' }}>
                    No submissions recorded yet. Click "Test Submission" to add one!
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </TableCard>

      <DetailModal
        open={Boolean(selectedSubmission)}
        submission={selectedSubmission}
        onClose={() => setSelectedSubmission(null)}
      />
    </div>
  );
}

