// Base components
export { Button } from './Button';
export type { ButtonProps } from './Button';

export { Input } from './Input';
export type { InputProps } from './Input';

export { Textarea } from './Textarea';
export type { TextareaProps } from './Textarea';

export { Select } from './Select';
export type { SelectProps, SelectOption } from './Select';

export { Checkbox, CheckboxGroup } from './Checkbox';
export type { CheckboxProps, CheckboxGroupProps } from './Checkbox';

export { Radio, RadioGroup, RadioCards } from './Radio';
export type { RadioProps, RadioGroupProps, RadioCardsProps, RadioCardOption } from './Radio';

export { Switch, LabeledSwitch } from './Switch';
export type { SwitchProps, LabeledSwitchProps } from './Switch';

// Layout components
export { Card, CardHeader, CardTitle, CardContent, CardFooter, StatCard } from './Card';
export type { CardProps, CardHeaderProps, CardTitleProps, CardContentProps, CardFooterProps, StatCardProps } from './Card';

export { Modal, ModalFooter } from './Modal';
export type { ModalProps, ModalFooterProps } from './Modal';

export { Tabs, TabList, TabTrigger, TabContent } from './Tabs';
export type { TabsProps, TabListProps, TabTriggerProps, TabContentProps } from './Tabs';

// Data display
export { Table, Pagination } from './Table';
export type { TableProps, Column, SortDirection, PaginationProps } from './Table';

export { Badge, StatusBadge } from './Badge';
export type { BadgeProps, BadgeVariant, BadgeSize, StatusBadgeProps, StatusType } from './Badge';

export { Avatar, AvatarGroup } from './Avatar';
export type { AvatarProps, AvatarSize, AvatarGroupProps } from './Avatar';

export { Tooltip, InfoTooltip } from './Tooltip';
export type { TooltipProps, TooltipPosition, InfoTooltipProps } from './Tooltip';

// Feedback
export { ToastProvider, useToast } from './Toast';
export type { Toast, ToastType } from './Toast';

export { Alert, InlineAlert, BannerAlert } from './Alert';
export type { AlertProps, AlertVariant, InlineAlertProps, BannerAlertProps } from './Alert';

export { Spinner, LoadingOverlay, LoadingDots, Skeleton, SkeletonText, SkeletonCard, SkeletonTable } from './Spinner';
export type { SpinnerProps, SpinnerSize, LoadingOverlayProps, SkeletonProps } from './Spinner';

export { Progress, CircularProgress, StepsProgress } from './Progress';
export type { ProgressProps, ProgressVariant, ProgressSize, CircularProgressProps, StepsProgressProps, Step } from './Progress';

export { EmptyState, NoData, NoSearchResults, ErrorState } from './EmptyState';
export type { EmptyStateProps, EmptyStateType, NoDataProps } from './EmptyState';
export { ActionError } from './ActionError';

// Dialogs
export { ConfirmDialog, DeleteConfirm, LogoutConfirm, UnsavedChangesConfirm } from './ConfirmDialog';
export type { ConfirmDialogProps, ConfirmVariant, DeleteConfirmProps, LogoutConfirmProps, UnsavedChangesConfirmProps } from './ConfirmDialog';

// Navigation
export { Breadcrumb, PageHeader } from './Breadcrumb';
export type { BreadcrumbProps, BreadcrumbItem, PageHeaderProps } from './Breadcrumb';

export { Dropdown, DropdownItem, DropdownSeparator, DropdownLabel, SelectDropdown } from './Dropdown';
export type { DropdownProps, DropdownItemProps, DropdownPosition, SelectDropdownProps, SelectDropdownOption } from './Dropdown';

// Inputs
export { SearchInput, SearchWithSuggestions } from './SearchInput';
export type { SearchInputProps, SearchWithSuggestionsProps, SearchSuggestion } from './SearchInput';

export { DatePicker, DateRangePicker } from './DatePicker';
export type { DatePickerProps, DateRangePickerProps } from './DatePicker';

export { PeriodPicker, DEFAULT_PRESETS, getDefaultPeriodValue } from './PeriodPicker';
export type { PeriodPickerProps, PeriodValue, PeriodPreset } from './PeriodPicker';

export { FileUpload } from './FileUpload';
export type { FileUploadProps, FileWithPreview } from './FileUpload';

// Existing components
export { default as SmartFilters } from './SmartFilters';
export type { FilterOption, FilterConfig, FilterSuggestion, FilterPreset, SmartFiltersProps } from './SmartFilters';

// S3 — Composants UI transversaux
export { MoneyInput } from './MoneyInput';
export type { MoneyInputProps } from './MoneyInput';

export { LiveTotal } from './LiveTotal';

export { StepperForm } from './StepperForm';
export type { StepperFormProps, StepDef } from './StepperForm';

export { TimelineAudit } from './TimelineAudit';
export type { TimelineEntry } from './TimelineAudit';

// SignaturePad, QRScanner, PDFDownloadButton : imports directs uniquement
// (deps lourdes : @zxing 411KB, react-signature-canvas 15KB)
// import { QRScanner } from '@shared/components/ui/QRScanner'
// import { SignaturePad } from '@shared/components/ui/SignaturePad'
// import { PDFDownloadButton } from '@shared/components/ui/PDFDownloadButton'

export { StockIndicator } from './StockIndicator';
export type { StockIndicatorProps } from './StockIndicator';

export { FilterBar } from './FilterBar';
export type { FilterBarProps, FilterChip } from './FilterBar';

export { SwipeActions } from './SwipeActions';
export type { SwipeActionsProps, SwipeAction } from './SwipeActions';

export { DomainStatusBadge } from './DomainStatusBadge';
export type { DomainStatusBadgeProps } from './DomainStatusBadge';

export { CountdownChip } from './CountdownChip';
export { PhotoGrid } from './PhotoGrid';

// UX List enhancements (v2)
export { KanbanBoard } from './KanbanBoard';
export type { KanbanBoardProps, KanbanColumn } from './KanbanBoard';

export { PaymentProgressBar } from './PaymentProgressBar';
export type { PaymentProgressBarProps } from './PaymentProgressBar';

export { DaySummaryBar } from './DaySummaryBar';
export type { DaySummaryBarProps, DaySummaryItem } from './DaySummaryBar';

export { StockLevelBar } from './StockLevelBar';
export type { StockLevelBarProps } from './StockLevelBar';

// Progressive image loading (MID → HIGH fidelity)
export { ImageWithLoading } from './ImageWithLoading';
export type { ImageWithLoadingProps } from './ImageWithLoading';

// Skeleton patterns (LOW fidelity per page type)
export {
  ImagePlaceholder,
  ReservationPhaseSkeleton,
  ListCardSkeleton,
  DetailPageSkeleton,
  ProductGridSkeleton,
  OperationSkeleton,
  FormSkeleton,
  DashboardSkeleton,
  PlanningSkeleton,
  SettingsSkeleton,
  ProfileSkeleton,
  InvoiceDetailSkeleton,
} from './SkeletonPatterns';
