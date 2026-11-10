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
} from '@mui/material';
import {
  Visibility as VisibilityIcon,
  Refresh as RefreshIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { getAllSubmissions, getForms } from '../services/api';
import DetailModal from '../components/DetailModal';

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

export default function SubmissionsPage({ initialFormId, onClearFormFilter }) {
  const [submissions, setSubmissions] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedForm, setSelectedForm] = useState(initialFormId || '');
  const [availableForms, setAvailableForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);

  useEffect(() => {
    getForms().then((forms) => setAvailableForms(forms)).catch(console.error);
  }, []);

  useEffect(() => {
    setSelectedForm(initialFormId || '');
    setCurrentPage(1);
  }, [initialFormId]);

  const fetchSubmissions = async (page = currentPage, formId = selectedForm) => {
    try {
      setLoading(true);
      const data = await getAllSubmissions(page, formId);
      setSubmissions(data.results || []);
      setTotalCount(data.count || 0);
    } catch (err) {
      console.error('Failed to load submissions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubmissions(currentPage, selectedForm);
  }, [currentPage, selectedForm]);

  const handleFormChange = (e) => {
    const val = e.target.value;
    setSelectedForm(val);
    setCurrentPage(1);
    if (!val && onClearFormFilter) onClearFormFilter();
  };

  const handleClearFilter = () => {
    setSelectedForm('');
    setCurrentPage(1);
    if (onClearFormFilter) onClearFormFilter();
  };

  const totalPages = Math.ceil(totalCount / 10) || 1;

  return (
    <div>
      <PageHeader>
        <div>
          <Typography variant="h5" sx={{ fontWeight: 700, color: '#0f172a' }}>
            Submissions Ledger
          </Typography>
          <Typography variant="body2" sx={{ color: '#64748b' }}>
            {selectedForm ? `Viewing submissions for form: ${selectedForm}` : 'All recorded form submissions (10 per page)'}
          </Typography>
        </div>

        <ControlsRow>
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="form-filter-label">Filter by Form</InputLabel>
            <Select
              labelId="form-filter-label"
              value={selectedForm}
              label="Filter by Form"
              onChange={handleFormChange}
            >
              <MenuItem value="">
                <em>All Forms</em>
              </MenuItem>
              {availableForms.map((f) => (
                <MenuItem key={f.form_id} value={f.form_id}>
                  {f.form_id} ({f.submission_count})
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
            <IconButton onClick={() => fetchSubmissions(currentPage, selectedForm)} sx={{ color: '#288474' }}>
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
                <TableCell>ID</TableCell>
                <TableCell>Form ID</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Idempotency Key</TableCell>
                <TableCell>Submission Date (UTC)</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                    <CircularProgress sx={{ color: '#288474' }} size={32} />
                  </TableCell>
                </TableRow>
              ) : submissions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 6, color: '#94a3b8' }}>
                    No submissions found.
                  </TableCell>
                </TableRow>
              ) : (
                submissions.map((sub) => (
                  <TableRow key={sub.id} hover sx={{ '& td': { borderBottom: '1px solid #f8fafc' } }}>
                    <TableCell sx={{ fontWeight: 600 }}>#{sub.id}</TableCell>
                    <TableCell>
                      <Chip
                        label={sub.form_id}
                        size="small"
                        onClick={() => setSelectedForm(sub.form_id)}
                        clickable
                        sx={{
                          backgroundColor: '#eef7f5',
                          color: '#288474',
                          fontWeight: 600,
                          fontSize: '12px',
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ color: '#0f172a' }}>{sub.email}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '12px', color: '#64748b' }}>
                      {sub.idempotency_key}
                    </TableCell>
                    <TableCell sx={{ fontSize: '13px', color: '#64748b' }}>
                      {new Date(sub.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        startIcon={<VisibilityIcon />}
                        onClick={() => setSelectedItem(sub)}
                        sx={{
                          color: '#288474',
                          textTransform: 'none',
                          fontWeight: 600,
                          '&:hover': { backgroundColor: '#eef7f5' },
                        }}
                      >
                        Details
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
            Showing {submissions.length > 0 ? (currentPage - 1) * 10 + 1 : 0} to{' '}
            {Math.min(currentPage * 10, totalCount)} of {totalCount.toLocaleString()} submissions
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

      <DetailModal
        open={Boolean(selectedItem)}
        submission={selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}

