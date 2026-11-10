import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  IconButton,
  Divider,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';

export default function DetailModal({ open, submission, onClose }) {
  if (!submission) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6" sx={{ fontWeight: 600, color: '#0f172a' }}>
          Submission #{submission.id} Details
        </Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
              FORM ID
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 600, color: '#0f172a' }}>
              <Chip
                label={submission.form_id}
                size="small"
                sx={{ backgroundColor: '#eef7f5', color: '#288474', fontWeight: 600, mt: 0.5 }}
              />
            </Typography>
          </Box>

          <Box>
            <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
              EMAIL
            </Typography>
            <Typography variant="body1" sx={{ color: '#0f172a' }}>
              {submission.email}
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
              {submission.idempotency_key}
            </Typography>
          </Box>

          <Box>
            <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600 }}>
              SUBMISSION DATE (UTC)
            </Typography>
            <Typography variant="body2" sx={{ color: '#0f172a', mt: 0.5 }}>
              {new Date(submission.created_at).toLocaleString()}
            </Typography>
          </Box>

          <Divider />

          <Box>
            <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600, mb: 1, display: 'block' }}>
              PAYLOAD DATA (JSON)
            </Typography>
            <Box
              component="pre"
              sx={{
                p: 2,
                backgroundColor: '#0f172a',
                color: '#38bdf8',
                borderRadius: '8px',
                fontSize: '13px',
                fontFamily: 'monospace',
                overflowX: 'auto',
                maxHeight: '240px',
              }}
            >
              {JSON.stringify(submission.data || {}, null, 2)}
            </Box>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} sx={{ color: '#64748b' }}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}
