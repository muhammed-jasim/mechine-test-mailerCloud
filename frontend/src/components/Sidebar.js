import React from 'react';
import styled from 'styled-components';
import {
  Dashboard as DashboardIcon,
  Description as DescriptionIcon,
  ListAlt as ListAltIcon,
  Timeline as TimelineIcon,
  AddCircleOutline as AddIcon,
} from '@mui/icons-material';

const SidebarContainer = styled.aside`
  width: 250px;
  background-color: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.02);
  user-select: none;
`;

const LogoSection = styled.div`
  padding: 24px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const LogoIcon = styled.div`
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background-color: #288474;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
`;

const LogoText = styled.div`
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.3px;
`;

const NavList = styled.nav`
  padding: 16px 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const NavItem = styled.button`
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  border: none;
  background: ${(props) => (props.active ? '#eef7f5' : 'transparent')};
  color: ${(props) => (props.active ? '#288474' : '#64748b')};
  font-weight: ${(props) => (props.active ? '600' : '500')};
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
  text-align: left;

  &:hover {
    background-color: ${(props) => (props.active ? '#eef7f5' : '#f8fafc')};
    color: ${(props) => (props.active ? '#288474' : '#0f172a')};
  }

  svg {
    font-size: 20px;
    color: ${(props) => (props.active ? '#288474' : '#94a3b8')};
  }
`;

const ActionSection = styled.div`
  padding: 16px;
  border-top: 1px solid #f1f5f9;
`;

const CreateButton = styled.button`
  width: 100%;
  padding: 11px 16px;
  border-radius: 8px;
  border: none;
  background-color: #288474;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(40, 132, 116, 0.25);
  transition: background-color 0.15s ease, transform 0.1s ease;

  &:hover {
    background-color: #216d60;
  }

  &:active {
    transform: translateY(1px);
  }
`;

export default function Sidebar({ currentTab, setTab, onOpenSubmitModal }) {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: <DashboardIcon /> },
    { id: 'forms', label: 'Forms', icon: <DescriptionIcon /> },
    { id: 'submissions', label: 'Submissions', icon: <ListAltIcon /> },
    { id: 'analytics', label: 'Analytics', icon: <TimelineIcon /> },
  ];

  return (
    <SidebarContainer>
      <LogoSection>
        <LogoIcon>F</LogoIcon>
        <div>
          <LogoText>FormEngine</LogoText>
          <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 500 }}>Live Analytics</div>
        </div>
      </LogoSection>

      <NavList>
        {navItems.map((item) => (
          <NavItem
            key={item.id}
            active={currentTab === item.id}
            onClick={() => setTab(item.id)}
          >
            {item.icon}
            {item.label}
          </NavItem>
        ))}
      </NavList>

      <ActionSection>
        <CreateButton onClick={onOpenSubmitModal}>
          <AddIcon fontSize="small" />
          Test Submission
        </CreateButton>
      </ActionSection>
    </SidebarContainer>
  );
}

