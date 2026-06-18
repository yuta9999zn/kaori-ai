'use client';
/**
 * Vietnamese-source translation map for static UI "chrome" — the P2 sidebar
 * (section headers + group + child titles in components/p2/navigation.ts) and
 * the dashboard KPI tile labels. These are hardcoded VN today and double as
 * React state/active-route keys, so we translate the DISPLAY only (keyed by
 * the VN source string) without restructuring NAV_TREE.
 *
 * VN is the source language → `vi` returns the key verbatim; a missing locale
 * falls back to the VN string (never a blank label). S7 will fold these into
 * the keyed dictionary.ts; until then this lets the sidebar + dashboard switch
 * across all 5 locales (vi/en/ja/ko/zh) immediately.
 */
import { useLocale } from './provider';
import type { Locale } from './dictionary';

type Tr = Partial<Record<Exclude<Locale, 'vi'>, string>>;

const CHROME: Record<string, Tr> = {
  'Dữ liệu & Pipeline': { en: 'Data & Pipeline', ja: 'データ＆パイプライン', ko: '데이터 & 파이프라인', zh: '数据与管道' },
  'Quy trình': { en: 'Process', ja: 'プロセス', ko: '프로세스', zh: '流程' },
  'Phân tích & Rủi ro': { en: 'Analysis & Risk', ja: '分析＆リスク', ko: '분석 & 리스크', zh: '分析与风险' },
  'Khách hàng & Báo cáo': { en: 'Customers & Reports', ja: '顧客＆レポート', ko: '고객 & 리포트', zh: '客户与报告' },
  'Hệ thống': { en: 'System', ja: 'システム', ko: '시스템', zh: '系统' },
  'Tổng quan': { en: 'Overview', ja: '概要', ko: '개요', zh: '概览' },
  'Bảng điều khiển': { en: 'Dashboard', ja: 'ダッシュボード', ko: '대시보드', zh: '仪表盘' },
  'Tuỳ chỉnh': { en: 'Customize', ja: 'カスタマイズ', ko: '사용자 지정', zh: '自定义' },
  'Dữ liệu': { en: 'Data', ja: 'データ', ko: '데이터', zh: '数据' },
  'Khám phá': { en: 'Explore', ja: '探索', ko: '탐색', zh: '探索' },
  'Bronze': { en: 'Bronze', ja: 'Bronze', ko: 'Bronze', zh: 'Bronze' },
  'Silver': { en: 'Silver', ja: 'Silver', ko: 'Silver', zh: 'Silver' },
  'Gold': { en: 'Gold', ja: 'Gold', ko: 'Gold', zh: 'Gold' },
  'Pipelines': { en: 'Pipelines', ja: 'パイプライン', ko: '파이프라인', zh: '管道' },
  'Lịch sử chạy': { en: 'Run History', ja: '実行履歴', ko: '실행 기록', zh: '运行历史' },
  'Tạo mới': { en: 'Create New', ja: '新規作成', ko: '새로 만들기', zh: '新建' },
  'Insight': { en: 'Insight', ja: 'インサイト', ko: '인사이트', zh: '洞察' },
  'Tất cả Insight': { en: 'All Insights', ja: 'すべてのインサイト', ko: '모든 인사이트', zh: '全部洞察' },
  'Tạo Insight': { en: 'Generate Insight', ja: 'インサイト生成', ko: '인사이트 생성', zh: '生成洞察' },
  'Knowledge Base': { en: 'Knowledge Base', ja: 'Knowledge Base', ko: 'Knowledge Base', zh: 'Knowledge Base' },
  'Biểu đồ': { en: 'Charts', ja: 'チャート', ko: '차트', zh: '图表' },
  'Chart Picker': { en: 'Chart Picker', ja: 'Chart Picker', ko: 'Chart Picker', zh: 'Chart Picker' },
  'Theo loại': { en: 'By Type', ja: 'タイプ別', ko: '유형별', zh: '按类型' },
  'Workflow': { en: 'Workflow', ja: 'ワークフロー', ko: '워크플로우', zh: '工作流' },
  'Phòng ban': { en: 'Departments', ja: '部門', ko: '부서', zh: '部门' },
  'Cơ cấu tổ chức': { en: 'Org Structure', ja: '組織構造', ko: '조직 구조', zh: '组织架构' },
  'Tất cả workflow': { en: 'All Workflows', ja: 'すべてのワークフロー', ko: '모든 워크플로우', zh: '全部工作流' },
  'Hợp đồng': { en: 'Contracts', ja: '契約', ko: '계약', zh: '合同' },
  'Duyệt & Phân quyền': { en: 'Approvals & Access', ja: '承認＆権限', ko: '승인 & 권한', zh: '审批与权限' },
  'Kho tài liệu': { en: 'Document Store', ja: '文書庫', ko: '문서 저장소', zh: '文档库' },
  'Quyết định': { en: 'Decisions', ja: '意思決定', ko: '의사결정', zh: '决策' },
  'Nhật ký quyết định': { en: 'Decision Log', ja: '意思決定ログ', ko: '의사결정 로그', zh: '决策日志' },
  'Phân quyền': { en: 'Access Control', ja: 'アクセス権限', ko: '접근 권한', zh: '权限管理' },
  'RBAC': { en: 'RBAC', ja: 'RBAC', ko: 'RBAC', zh: 'RBAC' },
  'Vai trò tuỳ chỉnh': { en: 'Custom Roles', ja: 'カスタムロール', ko: '사용자 지정 역할', zh: '自定义角色' },
  'ABAC builder': { en: 'ABAC builder', ja: 'ABAC builder', ko: 'ABAC builder', zh: 'ABAC builder' },
  'Mô phỏng': { en: 'Simulate', ja: 'シミュレーション', ko: '시뮬레이션', zh: '模拟' },
  'Audit': { en: 'Audit', ja: 'Audit', ko: 'Audit', zh: 'Audit' },
  'Phân tích': { en: 'Analysis', ja: '分析', ko: '분석', zh: '分析' },
  'Cơ bản': { en: 'Basic', ja: '基礎', ko: '기본', zh: '基础' },
  'Trung cấp': { en: 'Intermediate', ja: '中級', ko: '중급', zh: '中级' },
  'Nâng cao': { en: 'Advanced', ja: '上級', ko: '고급', zh: '高级' },
  'Phạm vi': { en: 'Scope', ja: '範囲', ko: '범위', zh: '范围' },
  'Khung phân tích': { en: 'Frameworks', ja: '分析フレームワーク', ko: '분석 프레임워크', zh: '分析框架' },
  'SWOT': { en: 'SWOT', ja: 'SWOT', ko: 'SWOT', zh: 'SWOT' },
  '6W': { en: '6W', ja: '6W', ko: '6W', zh: '6W' },
  '2H': { en: '2H', ja: '2H', ko: '2H', zh: '2H' },
  'Fishbone': { en: 'Fishbone', ja: 'Fishbone', ko: 'Fishbone', zh: 'Fishbone' },
  'MoM/YoY': { en: 'MoM/YoY', ja: 'MoM/YoY', ko: 'MoM/YoY', zh: 'MoM/YoY' },
  'Chiến lược': { en: 'Strategy', ja: '戦略', ko: '전략', zh: '战略' },
  'OKR': { en: 'OKR', ja: 'OKR', ko: 'OKR', zh: 'OKR' },
  'Lộ trình': { en: 'Roadmap', ja: 'ロードマップ', ko: '로드맵', zh: '路线图' },
  'Họp review': { en: 'Review Meetings', ja: 'レビュー会議', ko: '리뷰 미팅', zh: '复盘会议' },
  'Giá trị AI': { en: 'AI Value', ja: 'AI価値', ko: 'AI 가치', zh: 'AI 价值' },
  'NOV & ROI': { en: 'NOV & ROI', ja: 'NOV・ROI', ko: 'NOV & ROI', zh: 'NOV 与 ROI' },
  'Rủi ro': { en: 'Risk', ja: 'リスク', ko: '리스크', zh: '风险' },
  'Danh sách': { en: 'List', ja: '一覧', ko: '목록', zh: '列表' },
  'Xuất': { en: 'Export', ja: 'エクスポート', ko: '내보내기', zh: '导出' },
  'Cảnh báo': { en: 'Alerts', ja: 'アラート', ko: '알림', zh: '告警' },
  'Khách hàng': { en: 'Customers', ja: '顧客', ko: '고객', zh: '客户' },
  'Rủi ro & ROI': { en: 'Risk & ROI', ja: 'リスク＆ROI', ko: '리스크 & ROI', zh: '风险与ROI' },
  'Người dùng': { en: 'Users', ja: 'ユーザー', ko: '사용자', zh: '用户' },
  'Mời người': { en: 'Invite', ja: '招待', ko: '초대', zh: '邀请' },
  'Báo cáo': { en: 'Reports', ja: 'レポート', ko: '리포트', zh: '报告' },
  'Tự động': { en: 'Automated', ja: '自動', ko: '자동', zh: '自动' },
  'Builder': { en: 'Builder', ja: 'Builder', ko: 'Builder', zh: 'Builder' },
  'Mẫu': { en: 'Templates', ja: 'テンプレート', ko: '템플릿', zh: '模板' },
  'Tuân thủ AI': { en: 'AI Compliance', ja: 'AIコンプライアンス', ko: 'AI 컴플라이언스', zh: 'AI 合规' },
  'EU AI Act': { en: 'EU AI Act', ja: 'EU AI Act', ko: 'EU AI Act', zh: 'EU AI Act' },
  'Gói cước': { en: 'Plan', ja: 'プラン', ko: '요금제', zh: '套餐' },
  'Nâng cấp': { en: 'Upgrade', ja: 'アップグレード', ko: '업그레이드', zh: '升级' },
  'Thương hiệu': { en: 'Branding', ja: 'ブランディング', ko: '브랜딩', zh: '品牌' },
  'Email': { en: 'Email', ja: 'Email', ko: 'Email', zh: 'Email' },
  'Tài liệu': { en: 'Docs', ja: 'ドキュメント', ko: '문서', zh: '文档' },
  'Cài đặt': { en: 'Settings', ja: '設定', ko: '설정', zh: '设置' },
  'Doanh thu đã cứu (North Star)': { en: 'Revenue Saved (North Star)', ja: '回収した売上 (North Star)', ko: '되찾은 매출 (North Star)', zh: '已挽回收入 (North Star)' },
  'Doanh thu rủi ro': { en: 'Revenue at Risk', ja: 'リスク売上', ko: '위험 매출', zh: '风险收入' },
  'Khách đã xử lý': { en: 'Customers Handled', ja: '対応済み顧客', ko: '처리된 고객', zh: '已处理客户' },
  'Hạn mức khách / tháng (K-11)': { en: 'Customer Quota / Month (K-11)', ja: '顧客上限 / 月 (K-11)', ko: '고객 한도 / 월 (K-11)', zh: '客户配额 / 月 (K-11)' },
};

/** Translate a VN-source chrome label to the given locale (VN/missing → verbatim). */
export function translateChrome(vi: string, locale: Locale): string {
  if (locale === 'vi') return vi;
  return CHROME[vi]?.[locale] ?? vi;
}

/** Hook form — re-renders on locale change. `cT('Tổng quan')` → localized. */
export function useChromeT() {
  const { locale } = useLocale();
  return (vi: string) => translateChrome(vi, locale);
}
