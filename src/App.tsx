import { type ReactNode, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Divider,
  Drawer,
  Grid,
  IconButton,
  InputBase,
  LinearProgress,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Slider,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Add,
  Analytics,
  Article,
  Biotech,
  BubbleChart,
  CleaningServices,
  CloudUpload,
  Dashboard,
  Dataset,
  Download,
  FilterList,
  Groups,
  Insights,
  LocalHospital,
  Menu,
  MoreVert,
  NotificationsOutlined,
  Psychology,
  QueryStats,
  Science,
  Search,
  Send,
  Settings,
  SmartToy,
  TableChart,
  TaskAlt,
  UploadFile,
} from '@mui/icons-material';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getActivityRoute } from './activityRouting';
import {
  activities,
  NavKey,
  paperInsights,
} from './data';
import { clinicalAnalytics } from './clinicalData';
import { getPageTitle, navItems } from './navigation';
import { buildStudyReportText, toCsv } from './reporting';

const sidebarWidth = 292;
const enrollmentData = clinicalAnalytics.enrollmentData;
const ageData = clinicalAnalytics.ageData;
const diseaseData = clinicalAnalytics.diseaseData;
const qualityIssues = clinicalAnalytics.qualityIssues;
const patientRows = clinicalAnalytics.patientRows;
const cohortRows = clinicalAnalytics.cohortRows;
const navIcons: Record<NavKey, ReactNode> = {
  dashboard: <Dashboard />,
  datasets: <Dataset />,
  papers: <Article />,
  cohorts: <Groups />,
  reports: <Analytics />,
  simulator: <BubbleChart />,
};

type ActionHandler = (message: string) => void;

function downloadTextFile(filename: string, content: string, type = 'text/plain') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}


function App() {
  const [active, setActive] = useState<NavKey>('dashboard');
  const [chatInput, setChatInput] = useState('');
  const [notice, setNotice] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [uploadedDatasetName, setUploadedDatasetName] = useState(clinicalAnalytics.datasetName);
  const [uploadedPaperName, setUploadedPaperName] = useState('NEJM_2023_Cardio_Study_Final.pdf');
  const datasetInputRef = useRef<HTMLInputElement>(null);
  const paperInputRef = useRef<HTMLInputElement>(null);

  const notify: ActionHandler = (message) => setNotice(message);
  const requestDatasetUpload = () => datasetInputRef.current?.click();
  const requestPaperUpload = () => paperInputRef.current?.click();
  const exportDataset = () => {
    downloadTextFile('clinicalpilot-patient-preview.csv', toCsv(patientRows), 'text/csv');
    notify('Patient preview exported as CSV.');
  };
  const exportCohort = () => {
    downloadTextFile('clinicalpilot-cohort.csv', toCsv(cohortRows.map((row) => ({ ...row, diagnosis: row.diagnosis.join('; ') }))), 'text/csv');
    notify('Cohort export generated.');
  };
  const exportReport = () => {
    downloadTextFile('clinicalpilot-study-report.txt', buildStudyReportText(), 'text/plain');
    notify('Study report exported.');
  };

  const title = useMemo(() => getPageTitle(active, clinicalAnalytics.datasetName), [active]);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <input
        ref={datasetInputRef}
        type="file"
        hidden
        accept=".csv,.xlsx,.xls"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            setUploadedDatasetName(file.name);
            notify(`${file.name} staged for dataset profiling. The packaged demo analytics remain available locally.`);
          }
          event.target.value = '';
        }}
      />
      <input
        ref={paperInputRef}
        type="file"
        hidden
        accept=".pdf,.doc,.docx,.txt"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            setUploadedPaperName(file.name);
            notify(`${file.name} staged for paper insight extraction.`);
          }
          event.target.value = '';
        }}
      />
      <Sidebar active={active} onChange={setActive} onAction={notify} />
      <Drawer
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { width: sidebarWidth, bgcolor: '#eef2f6' },
        }}
      >
        <SidebarContent
          active={active}
          onChange={(key) => {
            setActive(key);
            setMobileNavOpen(false);
          }}
          onAction={(message) => {
            notify(message);
            setMobileNavOpen(false);
          }}
        />
      </Drawer>
      <Box sx={{ ml: { md: `${sidebarWidth}px` }, width: '100%', minWidth: 0 }}>
        <Topbar
          active={active}
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          onUploadDataset={requestDatasetUpload}
          onAction={notify}
          onOpenMobileNav={() => setMobileNavOpen(true)}
        />
        <Box component="main" sx={{ p: { xs: 2, lg: 4 }, maxWidth: 1500 }}>
          <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={2} sx={{ mb: 3 }}>
            <Box>
              <Typography variant="h4">{title}</Typography>
              <Typography color="text.secondary">
                {active === 'dashboard' && 'Clinical intelligence across trial operations, quality, and outcomes'}
                {active === 'datasets' && `${clinicalAnalytics.totalRows} records loaded from ${uploadedDatasetName} - HIPAA-style demo data`}
                {active === 'papers' && 'Project: Phase III Cardiovascular Trial Review'}
                {active === 'cohorts' && 'Explore and filter 24,500 active patient records'}
                {active === 'reports' && 'Create study-ready summaries from validated datasets'}
                {active === 'simulator' && 'Model recruitment, capacity, and staffing scenarios'}
              </Typography>
            </Box>
            <HeaderActions
              active={active}
              onAction={notify}
              onUploadDataset={requestDatasetUpload}
              onExportCohort={exportCohort}
              onExportReport={exportReport}
            />
          </Stack>

          {active === 'dashboard' && <DashboardView onAction={notify} onNavigate={setActive} />}
          {active === 'datasets' && <DatasetView chatInput={chatInput} setChatInput={setChatInput} onAction={notify} onExportDataset={exportDataset} />}
          {active === 'papers' && <PaperAnalyzerView paperName={uploadedPaperName} onUploadPaper={requestPaperUpload} onAction={notify} onExportReport={exportReport} />}
          {active === 'cohorts' && <CohortDiscoveryView onAction={notify} />}
          {active === 'reports' && <ReportsView chatInput={chatInput} setChatInput={setChatInput} onAction={notify} onExportReport={exportReport} />}
          {active === 'simulator' && <SimulatorView onAction={notify} />}
        </Box>
      </Box>
      <Snackbar
        open={Boolean(notice)}
        autoHideDuration={3600}
        onClose={() => setNotice('')}
        message={notice}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </Box>
  );
}

function Sidebar({ active, onChange, onAction }: { active: NavKey; onChange: (key: NavKey) => void; onAction: ActionHandler }) {
  return (
    <Box
      component="aside"
      sx={{
        display: { xs: 'none', md: 'flex' },
        position: 'fixed',
        inset: '0 auto 0 0',
        width: sidebarWidth,
        flexDirection: 'column',
        borderRight: '1px solid #d5dae1',
        bgcolor: '#eef2f6',
        p: 2,
        zIndex: 10,
      }}
    >
      <SidebarContent active={active} onChange={onChange} onAction={onAction} />
    </Box>
  );
}

function SidebarContent({ active, onChange, onAction }: { active: NavKey; onChange: (key: NavKey) => void; onAction: ActionHandler }) {
  return (
    <Box sx={{ display: 'flex', minHeight: '100%', flexDirection: 'column', p: 2 }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 4 }}>
        <Box sx={{ width: 48, height: 48, bgcolor: '#000', color: '#fff', display: 'grid', placeItems: 'center', borderRadius: 1 }}>
          <LocalHospital />
        </Box>
        <Box>
          <Typography variant="h5" sx={{ lineHeight: 1.05 }}>
            ClinicalPilot AI
          </Typography>
          <Typography variant="body2" color="text.secondary" fontWeight={700}>
            Clinical Research Suite
          </Typography>
        </Box>
      </Stack>

      <Button
        fullWidth
        variant="contained"
        color="secondary"
        startIcon={<Add />}
        onClick={() => onAction('New project workspace initialized for the packaged cardiovascular dataset.')}
        sx={{ mb: 3, bgcolor: '#000' }}
      >
        New Project
      </Button>

      <List sx={{ flex: 1 }}>
        {navItems.map((item) => (
          <ListItemButton
            key={item.key}
            selected={active === item.key}
            onClick={() => onChange(item.key)}
            sx={{
              mb: 1,
              borderRadius: 1,
              '&.Mui-selected': {
                bgcolor: '#7cebd8',
                color: '#00574d',
                '&:hover': { bgcolor: '#7cebd8' },
              },
            }}
          >
            <ListItemIcon sx={{ color: 'inherit', minWidth: 42 }}>{navIcons[item.key]}</ListItemIcon>
            <ListItemText primary={item.label} primaryTypographyProps={{ fontWeight: 800 }} />
          </ListItemButton>
        ))}
      </List>

      <ListItemButton sx={{ borderRadius: 1 }} onClick={() => onAction('Settings panel is enabled for local configuration review.')}>
        <ListItemIcon sx={{ minWidth: 42 }}>
          <Settings />
        </ListItemIcon>
        <ListItemText primary="Settings" primaryTypographyProps={{ fontWeight: 800 }} />
      </ListItemButton>
    </Box>
  );
}

function Topbar({
  active,
  searchTerm,
  setSearchTerm,
  onUploadDataset,
  onAction,
  onOpenMobileNav,
}: {
  active: NavKey;
  searchTerm: string;
  setSearchTerm: (value: string) => void;
  onUploadDataset: () => void;
  onAction: ActionHandler;
  onOpenMobileNav: () => void;
}) {
  return (
    <Stack
      direction="row"
      alignItems="center"
      justifyContent="space-between"
      spacing={2}
      sx={{ height: 72, px: { xs: 2, lg: 4 }, bgcolor: '#fff', borderBottom: '1px solid #d5dae1', position: 'sticky', top: 0, zIndex: 8 }}
    >
      <Tooltip title="Open navigation">
        <IconButton
          aria-label="Open navigation"
          onClick={onOpenMobileNav}
          sx={{ display: { xs: 'inline-flex', md: 'none' }, flexShrink: 0 }}
        >
          <Menu />
        </IconButton>
      </Tooltip>
      <Paper sx={{ display: 'flex', alignItems: 'center', px: 2, width: { xs: '100%', md: 430 }, minWidth: 0, bgcolor: '#f0f2f5' }}>
        <Search sx={{ color: 'text.secondary', mr: 1 }} />
        <InputBase
          fullWidth
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              onAction(searchTerm.trim() ? `Search queued for "${searchTerm.trim()}".` : 'Enter a search term to scan local clinical records.');
            }
          }}
          placeholder={
            active === 'papers'
              ? 'Search papers or findings...'
              : active === 'cohorts'
                ? 'Search patient database...'
                : 'Search datasets, cohorts, or trials...'
          }
        />
      </Paper>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ display: { xs: 'none', sm: 'flex' } }}>
        <Button variant="contained" startIcon={<UploadFile />} onClick={onUploadDataset}>
          Upload Dataset
        </Button>
        <Tooltip title="AI assistant">
          <IconButton onClick={() => onAction('Pilot AI assistant is active in the dataset and report panels.')}>
            <SmartToy />
          </IconButton>
        </Tooltip>
        <Tooltip title="Notifications">
          <IconButton onClick={() => onAction('No unresolved system notifications. Data-quality alerts remain visible on the dashboard.')}>
            <NotificationsOutlined />
          </IconButton>
        </Tooltip>
        <Avatar sx={{ bgcolor: '#00796b' }}>SC</Avatar>
      </Stack>
    </Stack>
  );
}

function HeaderActions({
  active,
  onAction,
  onUploadDataset,
  onExportCohort,
  onExportReport,
}: {
  active: NavKey;
  onAction: ActionHandler;
  onUploadDataset: () => void;
  onExportCohort: () => void;
  onExportReport: () => void;
}) {
  if (active === 'papers') {
    return (
      <Stack direction="row" spacing={1}>
        <Button variant="outlined" startIcon={<Insights />} onClick={() => onAction('Paper insight summary prepared for sharing.')}>Share Insights</Button>
        <Button variant="contained" startIcon={<Download />} onClick={onExportReport}>Export Report</Button>
      </Stack>
    );
  }
  if (active === 'cohorts') {
    return (
      <Stack direction="row" spacing={1}>
        <Button variant="outlined" onClick={() => onAction('Current cohort search saved locally for this session.')}>Save Search</Button>
        <Button variant="contained" startIcon={<Download />} onClick={onExportCohort}>Export Cohort</Button>
      </Stack>
    );
  }
  if (active === 'reports') {
    return <Button variant="contained" startIcon={<Add />} onClick={() => onAction('New study report draft created from the active dataset.')}>Create New Report</Button>;
  }
  return <Button variant="contained" startIcon={<CloudUpload />} onClick={onUploadDataset}>Upload Dataset</Button>;
}

function DashboardView({ onAction, onNavigate }: { onAction: ActionHandler; onNavigate: (key: NavKey) => void }) {
  return (
    <Stack spacing={3}>
      <Paper sx={{ p: { xs: 3, md: 5 }, bgcolor: '#101928', color: '#d9e2ee', border: '1px solid #172437' }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="h6" color="#8f9bb0" sx={{ maxWidth: 760, lineHeight: 1.6 }}>
              Analysis completed for the packaged cardiovascular dataset. <Box component="span" color="#00a58d" fontWeight={900}>Significant findings include a {clinicalAnalytics.diabeticHypertensionPercent}% hypertension rate among diabetic patients</Box>, computed directly from the sample records.
            </Typography>
          </Grid>
          <Grid item xs={12} md={4}>
            <Typography variant="body2" fontWeight={800} color="#8f9bb0">Processing Confidence</Typography>
            <LinearProgress variant="determinate" value={clinicalAnalytics.qualityScore} sx={{ my: 1.5, height: 9, borderRadius: 99, bgcolor: '#203044' }} />
            <Button
              fullWidth
              variant="outlined"
              onClick={() => onAction(`Deep analysis complete: ${clinicalAnalytics.diabeticHypertensionPercent}% diabetic-hypertension overlap and ${clinicalAnalytics.qualityScore}% quality score.`)}
              sx={{ color: '#7cebd8', borderColor: '#00796b' }}
            >
              Deep Analysis
            </Button>
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={2.5}>
        <MetricCard title="Total Patients" value={clinicalAnalytics.totalPatients.toLocaleString()} sub={`${clinicalAnalytics.totalRows} dataset rows including duplicates`} icon={<Groups />} trend="Live" />
        <MetricCard title="Average Age" value={clinicalAnalytics.averageAge.toString()} sub={`${clinicalAnalytics.genderFemalePercent}% female in packaged cohort`} icon={<QueryStats />} trend="Years" />
        <MetricCard title="Data Quality Score" value={`${clinicalAnalytics.qualityScore}%`} sub={`${clinicalAnalytics.missingBpCount} BP gaps, ${clinicalAnalytics.duplicateCount} duplicate ID`} icon={<TaskAlt />} trend="Computed" />
      </Grid>

      <Grid container spacing={2.5}>
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Box>
                  <Typography variant="h6">Enrollment Trends</Typography>
                  <Typography color="text.secondary">Cumulative patient enrollment over 6 months</Typography>
                </Box>
                <Tabs value={1}>
                  <Tab label="Daily" />
                  <Tab label="Monthly" />
                </Tabs>
              </Stack>
              <Box sx={{ height: 330 }}>
                <ResponsiveContainer>
                  <AreaChart data={enrollmentData}>
                    <defs>
                      <linearGradient id="enrollment" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00796b" stopOpacity={0.28} />
                        <stop offset="95%" stopColor="#00796b" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#edf0f3" vertical={false} />
                    <XAxis dataKey="month" axisLine={false} tickLine={false} />
                    <YAxis axisLine={false} tickLine={false} />
                    <ChartTooltip />
                    <Area type="monotone" dataKey="patients" stroke="#00796b" strokeWidth={3} fill="url(#enrollment)" />
                    <Line type="monotone" dataKey="target" stroke="#98a2b3" strokeDasharray="4 4" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6">Disease Distribution</Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>Patient population breakdown</Typography>
              <Box sx={{ height: 220 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={diseaseData} dataKey="value" innerRadius={58} outerRadius={92} paddingAngle={2}>
                      {diseaseData.map((item) => <Cell key={item.name} fill={item.color} />)}
                    </Pie>
                    <ChartTooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
              {diseaseData.map((item) => (
                <Stack key={item.name} direction="row" justifyContent="space-between" sx={{ py: 0.6 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: item.color }} />
                    <Typography fontWeight={800}>{item.name}</Typography>
                  </Stack>
                  <Typography>{item.value}% ({item.count})</Typography>
                </Stack>
              ))}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={6}>
          <MissingDataCard onAction={onAction} />
        </Grid>
        <Grid item xs={12} md={6}>
          <ActivityCard onAction={onAction} onNavigate={onNavigate} />
        </Grid>
      </Grid>
    </Stack>
  );
}

function MetricCard({ title, value, sub, icon, trend }: { title: string; value: string; sub: string; icon: ReactNode; trend: string }) {
  return (
    <Grid item xs={12} md={4}>
      <Card>
        <CardContent>
          <Stack direction="row" justifyContent="space-between">
            <Typography fontWeight={900} color="text.secondary">{title}</Typography>
            <Box color="text.secondary">{icon}</Box>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="baseline" sx={{ mt: 1 }}>
            <Typography variant="h3">{value}</Typography>
            <Typography color="primary" fontWeight={900}>{trend}</Typography>
          </Stack>
          <Typography color="text.secondary">{sub}</Typography>
        </CardContent>
      </Card>
    </Grid>
  );
}

function MissingDataCard({ onAction }: { onAction: ActionHandler }) {
  const rows = [
    ['Blood Pressure', clinicalAnalytics.missingBpCount, '#c62828'],
    ['Diagnosis', clinicalAnalytics.missingDiagnosisCount, '#00796b'],
    ['Duplicate IDs', clinicalAnalytics.duplicateCount, '#d95f6a'],
  ] as const;
  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between">
          <Typography variant="h6">Missing Data Trends</Typography>
          <Chip color="error" label="Alert" size="small" />
        </Stack>
        <Stack spacing={2.3} sx={{ mt: 3 }}>
          {rows.map(([label, value, color]) => (
            <Box key={label}>
              <Stack direction="row" justifyContent="space-between">
                <Typography fontWeight={800}>{label}</Typography>
                <Typography fontWeight={900} color={color}>{value} issue{value === 1 ? '' : 's'}</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={Math.min(100, (value / clinicalAnalytics.totalRows) * 100)} sx={{ mt: 1, height: 9, borderRadius: 99, bgcolor: '#e8ecef', '& .MuiLinearProgress-bar': { bgcolor: color } }} />
            </Box>
          ))}
        </Stack>
        <Button sx={{ mt: 2.5 }} onClick={() => onAction(`${clinicalAnalytics.missingBpCount + clinicalAnalytics.missingDiagnosisCount + clinicalAnalytics.duplicateCount} data-quality items queued for cleaning.`)}>
          View Data Cleaning Queue
        </Button>
      </CardContent>
    </Card>
  );
}

function ActivityCard({ onAction, onNavigate }: { onAction: ActionHandler; onNavigate: (key: NavKey) => void }) {
  return (
    <Card>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" sx={{ mb: 2 }}>
          <Typography variant="h6">Recent Activities</Typography>
          <Button size="small" onClick={() => onAction(`${activities.length} recent activities loaded.`)}>View All</Button>
        </Stack>
        <Stack spacing={2}>
          {activities.map((activity, index) => {
            const route = getActivityRoute(activity);
            return (
            <ListItemButton
              key={activity}
              onClick={() => {
                if (route) {
                  onNavigate(route.target);
                  onAction(route.message);
                }
              }}
              sx={{ alignItems: 'center', borderRadius: 1, px: 1, py: 1.2 }}
            >
              <Stack direction="row" spacing={2} alignItems="center" sx={{ width: '100%' }}>
              <Avatar sx={{ bgcolor: index === 3 ? '#fde8e8' : index === 2 ? '#7cebd8' : '#e8f7f3', color: index === 3 ? '#c62828' : '#00796b' }}>
                {index === 0 ? <UploadFile /> : index === 1 ? <Article /> : index === 2 ? <Psychology /> : <TaskAlt />}
              </Avatar>
              <Box>
                <Typography fontWeight={900}>{activity}</Typography>
                <Typography color="text.secondary">{index === 0 ? 'Uploaded by Dr. Sarah Miller - 2 hours ago' : index === 1 ? 'System generated - 5 hours ago' : index === 2 ? 'Clinical cohort: Diabetes Focus - 1 day ago' : 'Mismatched timestamps detected - 2 days ago'}</Typography>
              </Box>
              </Stack>
            </ListItemButton>
          );
          })}
        </Stack>
      </CardContent>
    </Card>
  );
}

function DatasetView({
  chatInput,
  setChatInput,
  onAction,
  onExportDataset,
}: {
  chatInput: string;
  setChatInput: (value: string) => void;
  onAction: ActionHandler;
  onExportDataset: () => void;
}) {
  const [showIssuesOnly, setShowIssuesOnly] = useState(false);
  const visibleRows = showIssuesOnly ? patientRows.filter((row) => row.quality !== 'Clean') : patientRows;

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} xl={8}>
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          {qualityIssues.map((issue) => (
            <Grid key={issue.label} item xs={12} md={4}>
              <Card sx={{ borderLeft: `5px solid ${issue.severity === 'high' ? '#c62828' : issue.severity === 'medium' ? '#00796b' : '#000'}` }}>
                <CardContent>
                  <Typography color={issue.severity === 'high' ? 'error' : 'primary'} fontWeight={900} textTransform="uppercase">{issue.label}</Typography>
                  <Typography variant="h4" sx={{ mt: 2 }}>{issue.value}</Typography>
                  <Typography color="text.secondary">{issue.detail}</Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        <Card sx={{ mb: 3 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2.5 }}>
          <Typography fontWeight={900}>Patient Data Preview - {clinicalAnalytics.datasetName}</Typography>
            <Stack direction="row">
              <Tooltip title="Filter rows">
                <IconButton
                  color={showIssuesOnly ? 'primary' : 'default'}
                  onClick={() => {
                    setShowIssuesOnly((value) => !value);
                    onAction(showIssuesOnly ? 'Showing all patient preview rows.' : 'Filtered table to data-quality issues.');
                  }}
                >
                  <FilterList />
                </IconButton>
              </Tooltip>
              <Tooltip title="Download table"><IconButton onClick={onExportDataset}><Download /></IconButton></Tooltip>
            </Stack>
          </Stack>
          <DataTable rows={visibleRows} />
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6">Data Health Map</Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>Visualizing data integrity across cohorts</Typography>
            <Box sx={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={ageData}>
                  <CartesianGrid stroke="#edf0f3" vertical={false} />
                  <XAxis dataKey="range" axisLine={false} tickLine={false} />
                  <YAxis axisLine={false} tickLine={false} />
                  <ChartTooltip />
                  <Bar dataKey="value" fill="#00796b" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} xl={4}>
        <AssistantPanel chatInput={chatInput} setChatInput={setChatInput} context="dataset" onAction={onAction} />
      </Grid>
    </Grid>
  );
}

function DataTable({ rows }: { rows: typeof patientRows }) {
  return (
    <Table>
      <TableHead sx={{ bgcolor: '#f2f4f7' }}>
        <TableRow>
          {['PatientID', 'Age', 'Gender', 'Diagnosis', 'BP (mmHg)', 'Quality'].map((head) => (
            <TableCell key={head} sx={{ fontWeight: 900 }}>{head}</TableCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row, index) => (
          <TableRow key={`${row.id}-${index}`} sx={{ bgcolor: row.quality === 'Duplicate' ? '#eefcf8' : row.quality === 'Invalid' ? '#fff8f8' : 'inherit' }}>
            <TableCell>{row.id}</TableCell>
            <TableCell sx={{ color: row.age > 120 ? 'error.main' : 'inherit', fontWeight: row.age > 120 ? 900 : 500 }}>{row.age}</TableCell>
            <TableCell>{row.gender}</TableCell>
            <TableCell>{row.diagnosis}</TableCell>
            <TableCell sx={{ fontStyle: row.bp === 'Missing' ? 'italic' : 'normal', color: row.bp === 'Missing' ? 'text.secondary' : 'inherit' }}>{row.bp}</TableCell>
            <TableCell>
              <Chip
                size="small"
                label={row.quality}
                color={row.quality === 'Clean' ? 'success' : row.quality === 'Invalid' ? 'error' : 'default'}
                sx={{ fontWeight: 900 }}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function PaperAnalyzerView({
  paperName,
  onUploadPaper,
  onAction,
  onExportReport,
}: {
  paperName: string;
  onUploadPaper: () => void;
  onAction: ActionHandler;
  onExportReport: () => void;
}) {
  return (
    <Grid container spacing={3}>
      <Grid item xs={12} lg={7}>
        <Paper
          onClick={onUploadPaper}
          sx={{
            border: '2px dashed #b7bec8',
            p: 5,
            minHeight: 260,
            display: 'grid',
            placeItems: 'center',
            textAlign: 'center',
            bgcolor: '#fff',
            cursor: 'pointer',
          }}
        >
          <Stack alignItems="center" spacing={2}>
            <Avatar sx={{ width: 76, height: 76, bgcolor: '#7cebd8', color: '#00796b' }}>
              <CloudUpload fontSize="large" />
            </Avatar>
            <Typography variant="h5">Upload Research Paper</Typography>
            <Typography color="text.secondary" sx={{ maxWidth: 520 }}>
              Drag and drop your PDF here or browse local files. Support for large clinical documents.
            </Typography>
          </Stack>
        </Paper>

        <Card sx={{ mt: 3 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2.5, bgcolor: '#f6f7f9' }}>
            <Typography fontWeight={800}>{paperName}</Typography>
            <Stack direction="row">
              <IconButton onClick={() => onAction('Paper findings search focused on objective, methods, results, and limitations.')}><Search /></IconButton>
              <IconButton onClick={onExportReport}><Download /></IconButton>
              <IconButton onClick={() => onAction('Paper actions menu: summarize, annotate, export citations.') }><MoreVert /></IconButton>
            </Stack>
          </Stack>
          <Box sx={{ bgcolor: '#4a4f57', p: 3 }}>
            <Paper sx={{ minHeight: 590, maxWidth: 650, mx: 'auto', p: 6 }}>
              <Chip label="Annotated by AI" color="primary" sx={{ float: 'right' }} />
              <SkeletonLine width="65%" />
              <SkeletonLine width="44%" />
              <Box sx={{ mt: 5 }}>
                {Array.from({ length: 8 }).map((_, index) => (
                  <SkeletonLine key={index} width={`${index % 3 === 0 ? 88 : index % 2 === 0 ? 72 : 52}%`} highlight={index === 5} />
                ))}
              </Box>
              <Paper variant="outlined" sx={{ height: 150, mt: 7, display: 'grid', placeItems: 'center', color: 'text.secondary' }}>
                FIG 1.1: PRIMARY ENDPOINT ANALYSIS
              </Paper>
            </Paper>
          </Box>
        </Card>
      </Grid>
      <Grid item xs={12} lg={5}>
        <Card>
          <CardContent>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
              <Insights color="primary" />
              <Typography variant="h5">AI Insights Extraction</Typography>
            </Stack>
            <Stack spacing={2}>
              {paperInsights.map((insight) => (
                <Paper
                  key={insight.title}
                  variant="outlined"
                  sx={{
                    p: 2.5,
                    borderLeft: `5px solid ${insight.tone === 'danger' ? '#c62828' : insight.tone === 'success' ? '#7cebd8' : insight.tone === 'primary' ? '#00796b' : '#d0d5dd'}`,
                    bgcolor: insight.tone === 'success' ? '#e4fbf7' : insight.tone === 'danger' ? '#fff8f8' : '#fff',
                  }}
                >
                  <Typography textTransform="uppercase" color={insight.tone === 'danger' ? 'error' : 'primary'} fontWeight={900} letterSpacing={1.5}>
                    {insight.title}
                  </Typography>
                  <Typography sx={{ mt: 1, fontSize: 18, lineHeight: 1.55 }}>{insight.body}</Typography>
                </Paper>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

function SkeletonLine({ width, highlight = false }: { width: string; highlight?: boolean }) {
  return <Box sx={{ height: 16, width, mb: 2, bgcolor: highlight ? '#c8fff5' : '#edf0f3' }} />;
}

function CohortDiscoveryView({ onAction }: { onAction: ActionHandler }) {
  const [minimumAge, setMinimumAge] = useState(60);
  const [maximumAge, setMaximumAge] = useState(95);
  const [minimumSystolic, setMinimumSystolic] = useState(140);
  const [selectedComorbidities, setSelectedComorbidities] = useState(['Diabetes Type 2']);
  const activeFilterCount = 2 + selectedComorbidities.length;
  const adjustedMatches = Math.max(
    0,
    clinicalAnalytics.cohortMatches.filter((row) => row.age >= minimumAge && row.age <= maximumAge && (row.systolicBP ?? 0) >= minimumSystolic).length -
      Math.max(0, selectedComorbidities.length - 1),
  );
  const adjustedShare = Number(((adjustedMatches / clinicalAnalytics.totalPatients) * 100).toFixed(2));

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} lg={3}>
        <Card sx={{ mb: 2.5 }}>
          <CardContent>
            <Stack direction="row" justifyContent="space-between">
              <Typography fontWeight={900}>Active Filters</Typography>
              <Button
                size="small"
                onClick={() => {
                  setMinimumAge(60);
                  setMaximumAge(95);
                  setMinimumSystolic(140);
                  setSelectedComorbidities(['Diabetes Type 2']);
                  onAction('Cohort filters reset to the default diabetes cohort.');
                }}
              >
                Clear All
              </Button>
            </Stack>
            <Divider sx={{ my: 1.5 }} />
            <Typography fontWeight={800}>Age Range</Typography>
            <Stack direction="row" spacing={1.2} sx={{ my: 1.2 }}>
              <TextField size="small" type="number" value={minimumAge} onChange={(event) => setMinimumAge(Number(event.target.value))} />
              <TextField size="small" type="number" value={maximumAge} onChange={(event) => setMaximumAge(Number(event.target.value))} />
            </Stack>
            <Typography fontWeight={800} sx={{ mt: 2 }}>Comorbidities</Typography>
            {['Diabetes Type 2', 'Hypertension', 'COPD'].map((label, index) => (
              <Stack key={label} direction="row" alignItems="center">
                <Checkbox
                  checked={selectedComorbidities.includes(label)}
                  onChange={(event) =>
                    setSelectedComorbidities((current) =>
                      event.target.checked ? [...current, label] : current.filter((item) => item !== label),
                    )
                  }
                />
                <Typography>{label}</Typography>
              </Stack>
            ))}
            <Typography fontWeight={800} sx={{ mt: 2 }}>Blood Pressure (Systolic)</Typography>
            <Slider value={minimumSystolic} min={90} max={190} valueLabelDisplay="auto" onChange={(_, value) => setMinimumSystolic(value as number)} />
            <Button fullWidth variant="outlined" color="secondary" onClick={() => onAction(`${adjustedMatches} patients match ${activeFilterCount} active cohort filters.`)}>
              Apply {activeFilterCount} Filters
            </Button>
          </CardContent>
        </Card>
        <Alert icon={<Analytics />} severity="success" sx={{ bgcolor: '#e0fbf7' }}>
          <Typography fontWeight={900}>Cohort Analysis</Typography>
          <Stack direction="row" justifyContent="space-between"><span>Matching Records</span><b>{adjustedMatches}</b></Stack>
          <Stack direction="row" justifyContent="space-between"><span>Population Share</span><b>{adjustedShare}%</b></Stack>
        </Alert>
      </Grid>
      <Grid item xs={12} lg={9}>
        <Card sx={{ mb: 2.5 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2.5, bgcolor: '#f5f7f9' }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <TaskAlt color="primary" />
              <Typography variant="h5">Protocol Eligibility Checker</Typography>
            </Stack>
            <Chip label="Pilot AI Powered" color="primary" />
          </Stack>
          <CardContent>
            <Grid container spacing={2.5}>
              <Grid item xs={12} md={7}>
                <Typography fontWeight={900} sx={{ mb: 1 }}>Paste Trial Inclusion/Exclusion Criteria</Typography>
                <TextField
                  fullWidth
                  multiline
                  minRows={7}
                  defaultValue="e.g. Adult patients aged 18-65 with documented Type 2 Diabetes for at least 12 months. Exclusion: History of severe renal impairment (eGFR < 30)."
                />
              </Grid>
              <Grid item xs={12} md={5}>
                <Paper variant="outlined" sx={{ p: 2.5, bgcolor: '#f3f5f7', height: '100%' }}>
                  <Typography fontWeight={900}>AI Discovery Results</Typography>
                  <Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}>
                    <Box>
                      <Typography>Eligible Patients</Typography>
                      <Typography variant="h3" color="primary">{clinicalAnalytics.protocolEligibleCount}</Typography>
                    </Box>
                    <Groups sx={{ fontSize: 48, color: '#b7d8d5' }} />
                  </Stack>
                  <Divider sx={{ my: 2 }} />
                  <Typography>Ineligible Patients</Typography>
                  <Typography variant="h3" color="text.secondary">{clinicalAnalytics.protocolIneligibleCount}</Typography>
                  <Button fullWidth variant="contained" color="secondary" sx={{ mt: 2 }} onClick={() => onAction(`${clinicalAnalytics.protocolEligibleCount} protocol-eligible patients identified; exclusions include kidney disease and age outside range.`)}>
                    Analyze Details
                  </Button>
                </Paper>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
        <CohortTable onAction={onAction} />
      </Grid>
    </Grid>
  );
}

function CohortTable({ onAction }: { onAction: ActionHandler }) {
  return (
    <Card>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2.5 }}>
        <Typography variant="h5">{clinicalAnalytics.cohortMatches.length} matching patients found</Typography>
        <Stack direction="row">
          <IconButton onClick={() => onAction('Cohort table filter tools opened.') }><FilterList /></IconButton>
          <IconButton onClick={() => onAction('Cohort table switched to structured table view.') }><TableChart /></IconButton>
        </Stack>
      </Stack>
      <Table>
        <TableHead sx={{ bgcolor: '#f2f4f7' }}>
          <TableRow>
            {['Patient ID', 'Age/Sex', 'Diagnosis', 'BP (Sys/Dia)', 'Last Lab Date', 'Match'].map((head) => <TableCell key={head} sx={{ fontWeight: 900 }}>{head}</TableCell>)}
          </TableRow>
        </TableHead>
        <TableBody>
          {cohortRows.map((row) => (
            <TableRow key={row.id}>
              <TableCell sx={{ color: 'primary.main', fontWeight: 900 }}>{row.id}</TableCell>
              <TableCell>{row.ageSex}</TableCell>
              <TableCell>
                <Stack direction="row" spacing={0.7} flexWrap="wrap">
                  {row.diagnosis.map((diagnosis) => <Chip key={diagnosis} size="small" label={diagnosis} color={diagnosis === 'Kidney Disease' ? 'info' : diagnosis === 'Hypertension' ? 'default' : 'error'} />)}
                </Stack>
              </TableCell>
              <TableCell>{row.bp}</TableCell>
              <TableCell>{row.lab}</TableCell>
              <TableCell><Chip label={`${row.match}%`} color="primary" sx={{ fontWeight: 900 }} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2.5 }}>
        <Typography>Showing 1-{cohortRows.length} of {clinicalAnalytics.cohortMatches.length} patients</Typography>
        <Stack direction="row" spacing={1}>
          {[1, 2, 3].map((page) => (
            <Button key={page} variant={page === 1 ? 'contained' : 'text'} onClick={() => onAction(`Cohort page ${page} selected.`)}>
              {page}
            </Button>
          ))}
        </Stack>
      </Stack>
    </Card>
  );
}

function ReportsView({
  chatInput,
  setChatInput,
  onAction,
  onExportReport,
}: {
  chatInput: string;
  setChatInput: (value: string) => void;
  onAction: ActionHandler;
  onExportReport: () => void;
}) {
  const [reportTitle, setReportTitle] = useState('Hypertension Efficacy Analysis Q3');
  const [reportType, setReportType] = useState('Detailed Analysis');
  const [aiEnabled, setAiEnabled] = useState(true);
  const reportTypes = ['Executive Summary', 'Detailed Analysis', 'Regulatory Submission'];

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} lg={3}>
        <Card>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h6">Report Configuration</Typography>
              <Chip label="Draft" color="primary" size="small" />
            </Stack>
            <Typography fontWeight={800} sx={{ mt: 3, mb: 1 }}>Report Title</Typography>
            <TextField fullWidth size="small" value={reportTitle} onChange={(event) => setReportTitle(event.target.value)} />
            <Typography fontWeight={800} sx={{ mt: 2, mb: 1 }}>Data Source</Typography>
            <Select fullWidth size="small" value={clinicalAnalytics.datasetName}>
              <MenuItem value={clinicalAnalytics.datasetName}>{clinicalAnalytics.datasetName}</MenuItem>
            </Select>
            <Typography fontWeight={800} sx={{ mt: 2, mb: 1 }}>Report Type</Typography>
            {reportTypes.map((label, index) => (
              <Paper
                key={label}
                variant="outlined"
                onClick={() => {
                  setReportType(label);
                  onAction(`${label} report format selected.`);
                }}
                sx={{ p: 1.5, mb: 1, bgcolor: reportType === label ? '#e9fbf8' : '#fff', borderColor: reportType === label ? '#00796b' : '#d7dde5', cursor: 'pointer' }}
              >
                <Typography fontWeight={900}>{label}</Typography>
                <Typography variant="body2" color="text.secondary">{index === 0 ? 'High-level insights for management' : index === 1 ? 'Deep dive into clinical outcomes' : 'FDA/EMA compliant format'}</Typography>
              </Paper>
            ))}
            <Divider sx={{ my: 2 }} />
            <Stack direction="row" spacing={1} alignItems="center">
              <Checkbox checked={aiEnabled} onChange={(event) => setAiEnabled(event.target.checked)} />
              <Typography fontWeight={800}>Enable AI Insight Generation</Typography>
            </Stack>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} lg={6}>
        <Card>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2, bgcolor: '#f5f7f9' }}>
            <Chip icon={<Insights />} label="AI-Generated Draft" color="primary" />
            <Stack direction="row">
              <IconButton onClick={() => onAction(`Searching generated report: ${reportTitle}`)}><Search /></IconButton>
              <IconButton onClick={onExportReport}><Download /></IconButton>
            </Stack>
          </Stack>
          <Box sx={{ bgcolor: '#e5e8ec', p: { xs: 2, md: 4 } }}>
            <Paper sx={{ maxWidth: 600, mx: 'auto', minHeight: 720, p: { xs: 3, md: 6 }, textAlign: 'center' }}>
              <Avatar sx={{ mx: 'auto', bgcolor: '#000', mb: 2 }}><LocalHospital /></Avatar>
              <Typography variant="h3">STUDY EFFICACY REPORT</Typography>
              <Typography variant="h6" sx={{ mt: 2 }}>{reportTitle}</Typography>
              <Divider sx={{ my: 4, borderColor: '#111' }} />
              <Typography variant="h6" color="primary" textAlign="left">1. Executive Summary</Typography>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                {[
                  ['Total Patients', clinicalAnalytics.totalPatients.toLocaleString()],
                  ['Average Age', `${clinicalAnalytics.averageAge} yrs`],
                  ['Trial Focus', 'Hypertension'],
                ].map(([label, value]) => (
                  <Grid item xs={4} key={label}>
                    <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'left' }}>
                      <Typography variant="caption" fontWeight={900} textTransform="uppercase">{label}</Typography>
                      <Typography variant="h5">{value}</Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
              <Alert severity="success" sx={{ mt: 4, textAlign: 'left' }}>
                AI summary: Compound-X controlled outcomes in {clinicalAnalytics.treatmentEffectiveness}% of treated patients, based on the packaged cardiovascular dataset.
              </Alert>
              <Box sx={{ height: 190, mt: 3 }}>
                <ResponsiveContainer>
                  <LineChart data={enrollmentData}>
                    <CartesianGrid stroke="#edf0f3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <ChartTooltip />
                    <Line type="monotone" dataKey="patients" stroke="#00796b" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            </Paper>
          </Box>
          <Stack direction="row" justifyContent="space-between" sx={{ p: 2, bgcolor: '#e5e8ec' }}>
            <Button variant="outlined" onClick={() => onAction(aiEnabled ? `${reportType} regenerated with current AI insight settings.` : 'AI insight generation is disabled for this draft.')}>
              Regenerate with AI
            </Button>
            <Button variant="contained" color="secondary" startIcon={<Download />} onClick={onExportReport}>Export Report</Button>
          </Stack>
        </Card>
      </Grid>
      <Grid item xs={12} lg={3}>
        <AssistantPanel chatInput={chatInput} setChatInput={setChatInput} context="report" onAction={onAction} />
      </Grid>
    </Grid>
  );
}

function AssistantPanel({
  chatInput,
  setChatInput,
  context,
  onAction,
}: {
  chatInput: string;
  setChatInput: (value: string) => void;
  context: 'dataset' | 'report';
  onAction: ActionHandler;
}) {
  const [messages, setMessages] = useState<string[]>([]);
  const sendMessage = () => {
    const question = chatInput.trim();
    if (!question) {
      onAction('Enter a question for Pilot AI first.');
      return;
    }
    const answer =
      context === 'dataset'
        ? `${clinicalAnalytics.diabeticHypertensionPercent}% of diabetic patients also have hypertension; ${clinicalAnalytics.missingBpCount} BP records still need review.`
        : `The active draft uses ${clinicalAnalytics.totalPatients} unique patients, a ${clinicalAnalytics.qualityScore}% quality score, and ${clinicalAnalytics.treatmentEffectiveness}% Compound-X controlled outcomes.`;
    setMessages((current) => [`Q: ${question}`, `A: ${answer}`, ...current].slice(0, 6));
    setChatInput('');
    onAction('Pilot AI generated a local clinical-data answer.');
  };

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', minHeight: 620 }}>
        <Typography variant="h6" color="primary">Pilot AI Assistant</Typography>
        <Typography color="text.secondary">Clinical intelligence active</Typography>
        <Box sx={{ flex: 1, mt: 4 }}>
          <Paper sx={{ p: 2.5, bgcolor: '#e0fbf7', mb: 2 }}>
            {context === 'dataset' ? (
              <Typography>
                I identified {clinicalAnalytics.missingBpCount} missing BP values, {clinicalAnalytics.duplicateCount} duplicate PatientID, and {clinicalAnalytics.invalidAgeCount} invalid age entry from {clinicalAnalytics.datasetName}. Diabetic patients have a {clinicalAnalytics.diabeticHypertensionPercent}% hypertension overlap.
              </Typography>
            ) : (
              <Typography>
                Quick suggestion: the generated report is using {clinicalAnalytics.totalPatients} unique patients and a {clinicalAnalytics.qualityScore}% quality score from {clinicalAnalytics.datasetName}.
              </Typography>
            )}
            <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
              <Button size="small" variant="contained" onClick={() => onAction(context === 'dataset' ? 'Median BP imputation preview prepared for missing values.' : 'Report recommendation accepted.')}>
                {context === 'dataset' ? 'Impute BP Values' : 'Yes, please'}
              </Button>
              <Button size="small" variant="outlined" onClick={() => onAction(context === 'dataset' ? 'Invalid entries flagged for source verification.' : 'Recommendation dismissed for this report draft.')}>
                {context === 'dataset' ? 'Flag Invalid Entries' : 'Not now'}
              </Button>
            </Stack>
          </Paper>
          <List>
            {['Dataset Cleaning', 'Chatbot Queries', 'Protocol Check'].map((item) => (
              <ListItemButton key={item} onClick={() => onAction(`${item} workflow opened in the assistant panel.`)}>
                <ListItemIcon><CleaningServices color="primary" /></ListItemIcon>
                <ListItemText primary={item} secondary={item === 'Dataset Cleaning' ? `${clinicalAnalytics.missingBpCount + clinicalAnalytics.duplicateCount + clinicalAnalytics.invalidAgeCount} issues pending fix` : item === 'Protocol Check' ? `${clinicalAnalytics.protocolEligibleCount} eligible patients` : `${clinicalAnalytics.diabeticHypertensionPercent}% diabetic-hypertension overlap`} />
              </ListItemButton>
            ))}
          </List>
          {messages.map((message) => (
            <Paper key={message} variant="outlined" sx={{ p: 1.5, mb: 1 }}>
              <Typography variant="body2">{message}</Typography>
            </Paper>
          ))}
        </Box>
        <Paper sx={{ display: 'flex', alignItems: 'center', p: 1.2, bgcolor: '#f0f2f5' }}>
          <InputBase
            fullWidth
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') sendMessage();
            }}
            placeholder="Ask ClinicalPilot AI..."
          />
          <IconButton color="primary" onClick={sendMessage}><Send /></IconButton>
        </Paper>
      </CardContent>
    </Card>
  );
}

function SimulatorView({ onAction }: { onAction: ActionHandler }) {
  const [enrollmentIncrease, setEnrollmentIncrease] = useState(20);
  const [clinicCapacity, setClinicCapacity] = useState(82);
  const [staffingBuffer, setStaffingBuffer] = useState(12);
  const [simulationRun, setSimulationRun] = useState(false);
  const staffingNeed = Math.max(1, Math.round((enrollmentIncrease + 20) / 20 - staffingBuffer / 18));
  const completionDelta = Math.round((enrollmentIncrease / 5) + (clinicCapacity - 80) / 10);
  const capacityRisk = Math.max(0, Math.round(100 - clinicalAnalytics.qualityScore + Math.max(0, enrollmentIncrease - clinicCapacity / 3)));

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} lg={5}>
        <Card>
          <CardContent>
            <Stack direction="row" spacing={1} alignItems="center">
              <Science color="primary" />
              <Typography variant="h5">Recruitment Scenario</Typography>
            </Stack>
            <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>
              Simulate how enrollment changes affect staffing, site capacity, and projected completion dates.
            </Typography>
            <Typography fontWeight={900}>Enrollment Increase</Typography>
            <Slider value={enrollmentIncrease} min={-20} max={60} valueLabelDisplay="auto" onChange={(_, value) => setEnrollmentIncrease(value as number)} />
            <Typography fontWeight={900}>Clinic Capacity</Typography>
            <Slider value={clinicCapacity} min={40} max={120} valueLabelDisplay="auto" onChange={(_, value) => setClinicCapacity(value as number)} />
            <Typography fontWeight={900}>Staffing Buffer</Typography>
            <Slider value={staffingBuffer} min={0} max={35} valueLabelDisplay="auto" onChange={(_, value) => setStaffingBuffer(value as number)} />
            <Button
              fullWidth
              variant="contained"
              sx={{ mt: 2 }}
              onClick={() => {
                setSimulationRun(true);
                onAction(`Simulation run: ${enrollmentIncrease}% enrollment change, ${clinicCapacity}% capacity, ${staffingBuffer}% staffing buffer.`);
              }}
            >
              Run Simulation
            </Button>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} lg={7}>
        <Card>
          <CardContent>
            <Typography variant="h5">Projected Impact</Typography>
            {simulationRun && <Chip label="Scenario updated" color="primary" sx={{ mt: 1 }} />}
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <MetricCard title="Staffing Need" value={`+${staffingNeed} FTE`} sub={`${clinicalAnalytics.totalPatients} active sample patients modeled`} icon={<Groups />} trend={staffingNeed > 2 ? 'High' : 'Moderate'} />
              <MetricCard title="Completion Date" value={`${completionDelta >= 0 ? '-' : '+'}${Math.abs(completionDelta)} days`} sub="Projected closeout change from scenario sliders" icon={<TaskAlt />} trend={completionDelta >= 0 ? 'Improved' : 'Delayed'} />
              <MetricCard title="Capacity Risk" value={`${capacityRisk}%`} sub="Derived from data quality, enrollment, and capacity" icon={<Biotech />} trend={capacityRisk > 25 ? 'High' : 'Watch'} />
            </Grid>
            <Box sx={{ height: 330, mt: 3 }}>
              <ResponsiveContainer>
                <AreaChart data={enrollmentData}>
                  <CartesianGrid stroke="#edf0f3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <ChartTooltip />
                  <Area type="monotone" dataKey="patients" stroke="#00796b" fill="#7cebd8" fillOpacity={0.35} />
                  <Area type="monotone" dataKey="target" stroke="#111827" fill="#d9dee6" fillOpacity={0.35} />
                </AreaChart>
              </ResponsiveContainer>
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

export default App;
