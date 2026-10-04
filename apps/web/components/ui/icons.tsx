import type { ReactNode, SVGProps } from "react";

/**
 * Small inline icon set (24px grid, 1.75 stroke). Decorative by default
 * (aria-hidden); pass `title` or an aria-label when an icon stands alone.
 */
type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 18, children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={props["aria-label"] ? undefined : true}
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const ChatIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-3.9A8 8 0 1 1 20 12Z" />
  </Icon>
);
export const MicIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
  </Icon>
);
export const GaugeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 17a8 8 0 1 1 16 0" />
    <path d="m12 17 3.5-5" />
  </Icon>
);
export const FileIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </Icon>
);
export const ReportIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </Icon>
);
export const KeyIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="8" cy="15" r="4" />
    <path d="m11 12 9-9M16 7l3 3" />
  </Icon>
);
export const UsersIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20c.6-3.4 3.2-5.5 6.5-5.5s5.9 2.1 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.8c1.9.7 3.2 2.5 3.5 5.2" />
  </Icon>
);
export const BookIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5v-15Z" />
    <path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3M9 7.5h6" />
  </Icon>
);
export const BellIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9Z" />
    <path d="M10 19a2 2 0 0 0 4 0" />
  </Icon>
);
export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </Icon>
);
export const XIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Icon>
);
export const AlertIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3.5 2.8 19.5h18.4L12 3.5Z" />
    <path d="M12 10v4.5M12 17.4v.1" />
  </Icon>
);
export const InfoIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 7.9v.1" />
  </Icon>
);
export const SparkleIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.600-.6 6.400-2.400 7-7Z" />
    <path d="M19 16.5v3M17.500 18h3" />
  </Icon>
);
export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
);
export const ChevronRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m9 6 6 6-6 6" />
  </Icon>
);
export const SignOutIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9" />
  </Icon>
);
export const UploadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 16V4M7 9l5-5 5 5M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
  </Icon>
);
export const ClockIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icon>
);
export const CodeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m8 8-4 4 4 4M16 8l4 4-4 4M13.500 5l-3 14" />
  </Icon>
);
export const ShieldIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3 5 6v5.500c0 4.500 3 8 7 9.500 4-1.500 7-5 7-9.500V6l-7-3Z" />
    <path d="m9 12 2.200 2.200L15.500 10" />
  </Icon>
);
export const SendIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M21 3 10 14M21 3l-6.500 18-3.500-7-7-3.500L21 3Z" />
  </Icon>
);
export const UserIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 20.500c.8-3.700 3.900-6 8-6s7.200 2.300 8 6" />
  </Icon>
);

export function GoogleIcon({ size = 18, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" focusable="false" {...props}>
      <path
        fill="#4285F4"
        d="M22.560 12.250c0-.780-.070-1.530-.200-2.250H12v4.260h5.920a5.060 5.060 0 0 1-2.200 3.320v2.770h3.560c2.080-1.920 3.280-4.740 3.280-8.100Z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.970 0 5.460-.980 7.280-2.660l-3.560-2.770c-.980.660-2.230 1.060-3.720 1.060-2.860 0-5.290-1.930-6.160-4.530H2.180v2.840A11 11 0 0 0 12 23Z"
      />
      <path
        fill="#FBBC05"
        d="M5.840 14.100A6.600 6.600 0 0 1 5.490 12c0-.730.130-1.430.350-2.100V7.070H2.180A11 11 0 0 0 1 12c0 1.780.430 3.460 1.180 4.930l3.660-2.830Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.380c1.620 0 3.060.560 4.210 1.640l3.150-3.150C17.450 2.090 14.970 1 12 1A11 11 0 0 0 2.180 7.070l3.660 2.830C6.710 7.310 9.140 5.380 12 5.380Z"
      />
    </svg>
  );
}

export const TrashIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12.5a1.5 1.5 0 0 0 1.5 1.5h7a1.5 1.5 0 0 0 1.5-1.5L18 7M9 7V4.5h6V7" />
  </Icon>
);
export const CopyIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V6a2 2 0 0 1 2-2h8" />
  </Icon>
);
export const RefreshIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 11a8 8 0 0 0-14-4.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4.5L20 15M20 20v-5h-5" />
  </Icon>
);
export const PlusIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
export const ArrowLeftIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M19 12H5m6-6-6 6 6 6" />
  </Icon>
);
export const PencilIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m4 20 1-4L16.5 4.5a2 2 0 0 1 3 3L8 19l-4 1ZM14 7l3 3" />
  </Icon>
);
