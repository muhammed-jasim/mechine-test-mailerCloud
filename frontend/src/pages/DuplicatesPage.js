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
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Clear as ClearIcon,
  ShieldOutlined as ShieldIcon,
  Visibility as VisibilityIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { getDuplicateLogs, getForms } from '../services/api';

const PageHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
`;

const ControlsRow = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const TableCard = styled.div`
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
`;

const PaginationFooter = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
`;

export default function DuplicatesPage() {
  const [logs, setLogs] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedForm, setSelectedForm] = useState('');
  const [availableForms, setAvailableForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState(null);

  useEffect(() => {
    getForms().then((f) => setAvailableForms(f)).catch(console.error);
  }, []);

  const fetchLogs = async (page = currentPage, formId = selectedForm) => {
    try {
      setLoading(true);
      const data = await getDuplicateLogs(page, formId);
      setLogs(data.results || []);
      setTotalCount(data.count || 0);
    } catch (err) {
      console.error('Failed to load duplicate logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs(currentPage, selectedForm);
  }, [currentPage, selectedForm]);

  const handleFormChange = (e) => {
    setSelectedForm(e.target.value);
    setCurrentPage(1);
  };

  const handleClearFilter = () => {
    setSelectedForm('');
    setCurrentPage(1);
  };

  const totalPages = Math.ceil(totalCount / 10) || 1;

  return (
    <div>
      <PageHeader>
        <div>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ShieldIcon sx={{ color: '#d97706', fontSize: 26 }} />
            <Typography variant="h5" sx={{ fontWeight: 700, color: '#0f172a' }}>
              Duplicate Interception Audit Trail
            </Typography>
          </Box>
          <Typography variant="body2" sx={{ color: '#64748b', mt: 0.5 }}>
            Real-time audit log of repeated idempotency keys intercepted and prevented from double-inserting
          </Typography>
        </div>

        <ControlsRow>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="dup-form-filter">Filter by Form</InputLabel>
            <Select
              labelId="dup-form-filter"
              value={selectedForm}
              label="Filter by Form"
              onChange={handleFormChange}
            >
              <MenuItem value="">
                <em>All Forms</em>
              </MenuItem>
              {availableForms.map((f) => (
                <MenuItem key={f.form_id} value={f.form_id}>
                  {f.form_id}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {selectedForm && (
            <Button
              size="small"
              variant="outlined"
              onClick={handleClearFilter}
              startIcon={<ClearIcon />}
              sx={{ borderColor: '#cbd5e1', color: '#64748b' }}
            >
              Clear Filter
            </Button>
          )}

          <Tooltip title="Refresh">
            <IconButton onClick={() => fetchLogs(currentPage, selectedForm)} sx={{ color: '#288474' }}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </ControlsRow>
      </PageHeader>

      <TableCard>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ '& th': { color: '#64748b', fontWeight: 600, borderBottom: '1px solid #f1f5f9' } }}>
                <TableCell>Log ID</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Form ID</TableCell>
                <TableCell>Idempotency Key</TableCell>
                <TableCell>Original Record</TableCell>
                <TableCell>Attempted Email</TableCell>
                <TableCell>Intercepted At (UTC)</TableCell>
                <TableCell align="right">Details</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 6 }}>
                    <CircularProgress sx={{ color: '#288474' }} size={32} />
                  </TableCell>
                </TableRow>
              ) : logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 6, color: '#94a3b8' }}>
                    No duplicate attempts detected yet. Send a submission with an existing idempotency key to test!
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log) => (
                  <TableRow key={log.id} hover sx={{ '& td': { borderBottom: '1px solid #f8fafc' } }}>
                    <TableCell sx={{ fontWeight: 600 }}>#{log.id}</TableCell>
                    <TableCell>
                      <Chip
                        label="INTERCEPTED"
                        size="small"
                        sx={{
                          backgroundColor: '#fef3c7',
                          color: '#d97706',
                          fontWeight: 700,
                          fontSize: '11px',
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={log.form_id}
                        size="small"
                        sx={{ backgroundColor: '#eef7f5', color: '#288474', fontWeight: 600, fontSize: '12px' }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '12px', color: '#64748b' }}>
                      {log.idempotency_key}
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, color: '#0f172a' }}>
                      #{log.original_submission_id}
                    </TableCell>
                    <TableCell sx={{ color: '#0f172a' }}>{log.attempted_email}</TableCell>
                    <TableCell sx={{ fontSize: '13px', color: '#64748b' }}>
                      {new Date(log.detected_at).toLocaleString()}
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        startIcon={<VisibilityIcon />}
                        onClick={() => setSelectedLog(log)}
                        sx={{
                          color: '#288474',
                          textTransform: 'none',
                          fontWeight: 600,
                          '&:hover': { backgroundColor: '#eef7f5' },
                        }}
                      >
                        Inspect
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        <PaginationFooter>
          <Typography variant="body2" sx={{ color: '#64748b' }}>
            Showing {logs.length > 0 ? (currentPage - 1) * 10 + 1 : 0} to{' '}
            {Math.min(currentPage * 10, totalCount)} of {totalCount.toLocaleString()} intercepted duplicates
          </Typography>

          <Pagination
            count={totalPages}
            page={currentPage}
            onChange={(e, val) => setCurrentPage(val)}
            color="primary"
            shape="rounded"
            size="small"
            sx={{
              '& .Mui-selected': {
                backgroundColor: '#288474 !important',
                color: '#ffffff',
              },
            }}
          />
        </PaginationFooter>
      </TableCard>

      {/* Detail Dialog */}
      <Dialog open={Boolean(selectedLog)} onClose={() => setSelectedLog(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ fontWeight: 600, color: '#0f172a' }}>
            Duplicate Interception #{selectedLog?.id}
          </Typography>
          <IconButton size="small" onClick={() => setSelectedLog(null)}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers>
          {selectedLog && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
                  ORIGINAL SUBMISSION RECORD
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 600, color: '#0f172a', mt: 0.5 }}>
                  Returned original submission #{selectedLog.original_submission_id} (HTTP 200 OK)
                </Typography>
              </Box>

              <Box>
                <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
                  IDEMPOTENCY KEY
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: 'monospace',
                    backgroundColor: '#f1f5f9',
                    p: 1,
                    borderRadius: '6px',
                    wordBreak: 'break-all',
                    color: '#334155',
                    mt: 0.5,
                  }}
                >
                  {selectedLog.idempotency_key}
                </Typography>
              </Box>

              <Box>
                <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
                  ATTEMPTED EMAIL
                </Typography>
                <Typography variant="body2" sx={{ color: '#0f172a', mt: 0.5 }}>
                  {selectedLog.attempted_email}
                </Typography>
              </Box>

              <Divider />

              <Box>
                <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600, mb: 1, display: 'block' }}>
                  ATTEMPTED PAYLOAD (JSON)
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    p: 2,
                    backgroundColor: '#0f172a',
                    color: '#f59e0b',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontFamily: 'monospace',
                    overflowX: 'auto',
                    maxHeight: '200px',
                  }}
                >
                  {JSON.stringify(selectedLog.attempted_data || {}, null, 2)}
                </Box>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setSelectedLog(null)} sx={{ color: '#64748b' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}
