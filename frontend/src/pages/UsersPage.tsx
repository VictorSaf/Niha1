import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  Search,
  Plus,
  Edit,
  Building2,
  Clock,
  RefreshCw,
  Trash2,
  Eye,
  CheckSquare,
  X,
  ShieldAlert,
} from 'lucide-react';
import { Button, Card, Badge, ConfirmationModal, Skeleton, showToast } from '../components/common';
import { BackofficeLayout } from '../components/layout';
import { AddAssetModal, EditAssetModal } from '../components/backoffice';
import {
  CreateUserModal,
  EditUserModal,
  PasswordResetModal,
  UserDetailModal,
} from '../components/users';
import { cn, formatRelativeTime } from '../utils';
import { getApiErrorMessage } from '../utils/errors';
import { buildDepositAndWithdrawalHistory } from '../utils/depositHistory';
import { adminApi, backofficeApi } from '../services/api';
import type { User, UserRole, AdminUserFull, Deposit, EntityBalance, DepositHistoryItem } from '../types';

/** Order for admin "advance role" click (flow roles only). */
// Simple interface for entity assets display (subset of full EntityAssets)
interface EntityAssetsDisplay {
  entityId: string;
  entityName: string;
  eurBalance: number;
  ceaBalance: number;
  euaBalance: number;
}

interface UserWithEntity extends User {
  entityName?: string;
  isActive?: boolean;
  createdAt?: string;
}

export function UsersPage() {
  const [users, setUsers] = useState<UserWithEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all' | 'DISABLED'>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState<UserWithEntity | null>(null);
  const [pagination, setPagination] = useState({ page: 1, total: 0, totalPages: 0 });
  const [savingUser, setSavingUser] = useState(false);

  // Create user form state
  const [newUser, setNewUser] = useState({
    email: '',
    firstName: '',
    lastName: '',
    position: '',
    password: '',
    role: 'NDA' as UserRole,
  });
  const [useInvitation, setUseInvitation] = useState(false);

  // Edit user form state
  const [editForm, setEditForm] = useState({
    firstName: '',
    lastName: '',
    position: '',
    role: 'NDA' as UserRole,
    isActive: true,
  });

  // User Detail Modal state
  const [detailUser, setDetailUser] = useState<AdminUserFull | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailTab, setDetailTab] = useState<'info' | 'auth' | 'sessions' | 'deposits' | 'orders'>('info');

  // Edit Asset modal state
  const [editingAsset, setEditingAsset] = useState<{
    entityId: string;
    entityName: string;
    assetType: 'EUR' | 'CEA' | 'EUA';
    currentBalance: number;
  } | null>(null);

  // Password Reset state
  const [showPasswordReset, setShowPasswordReset] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [forceChange, setForceChange] = useState(true);
  const [resettingPassword, setResettingPassword] = useState(false);

  // Deactivation confirmation modal state
  const [deactivateUser, setDeactivateUser] = useState<UserWithEntity | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkRole, setBulkRole] = useState<UserRole>('NDA');
  const [bulkLoading, setBulkLoading] = useState(false);

  // Add Asset modal state
  const [addAssetUser, setAddAssetUser] = useState<{ id: string; entityId: string; entityName: string } | null>(null);

  // Deposit state (view only - deposit creation is in backoffice)
  const [entityBalance, setEntityBalance] = useState<EntityBalance | null>(null);
  const [entityAssets, setEntityAssets] = useState<EntityAssetsDisplay | null>(null);
  const [deposits, setDeposits] = useState<Deposit[]>([]);
  const [depositAndWithdrawalHistory, setDepositAndWithdrawalHistory] = useState<DepositHistoryItem[]>([]);
  const [loadingDeposits, setLoadingDeposits] = useState(false);
  const [depositsError, setDepositsError] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      const params: { role?: UserRole | 'DISABLED'; search?: string; page: number; per_page: number } = {
        page: pagination.page,
        per_page: 20,
      };
      if (roleFilter !== 'all') {
        params.role = roleFilter;
      }
      if (searchQuery) {
        params.search = searchQuery;
      }

      const response = await adminApi.getUsers(params);
      setUsers(response.data);
      setPagination({
        page: response.pagination.page,
        total: response.pagination.total,
        totalPages: response.pagination.totalPages,
      });
    } catch (error) {
      console.error('Failed to load users:', error);
    } finally {
      setLoading(false);
    }
  }, [roleFilter, pagination.page, searchQuery]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // Handle search with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      if (pagination.page === 1) {
        loadUsers();
      } else {
        setPagination(prev => ({ ...prev, page: 1 }));
      }
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery]);

  const handleCreateUser = async () => {
    if (!newUser.email || !newUser.firstName || !newUser.lastName) return;
    if (newUser.role !== 'PREINTRODUCER' && !useInvitation && !newUser.password) return;

    setSavingUser(true);
    try {
      let created: User;

      if (newUser.role === 'PREINTRODUCER') {
        const result = await adminApi.createPreintroducer({
          email: newUser.email,
          first_name: newUser.firstName,
          last_name: newUser.lastName,
          position: newUser.position?.trim() || undefined,
        });
        created = {
          id: result.user.id,
          email: result.user.email,
          role: result.user.role as UserRole,
          referralCode: result.user.referral_code,
          firstName: newUser.firstName,
          lastName: newUser.lastName,
          position: newUser.position?.trim() || undefined,
        } as User;
      } else {
        const userData: {
          email: string; firstName: string; lastName: string;
          role: UserRole; password?: string; position?: string;
        } = {
          email: newUser.email,
          firstName: newUser.firstName,
          lastName: newUser.lastName,
          role: newUser.role,
        };
        if (!useInvitation && newUser.password) userData.password = newUser.password;
        if (newUser.position?.trim()) userData.position = newUser.position.trim();
        created = await adminApi.createUser(userData);
      }

      setUsers([created, ...users]);
      setShowCreateModal(false);
      setNewUser({ email: '', firstName: '', lastName: '', position: '', password: '', role: 'NDA' });
      setUseInvitation(false);
    } catch (error) {
      console.error('Failed to create user:', error);
      showToast('error', getApiErrorMessage(error), 'Create user');
    } finally {
      setSavingUser(false);
    }
  };

  const handleUpdateUser = async () => {
    if (!editingUser) return;

    setSavingUser(true);
    try {
      const payload: import('../types').AdminUserUpdate = {
        firstName: editForm.firstName,
        lastName: editForm.lastName,
        position: editForm.position,
        isActive: editForm.isActive,
      };
      // MM users: admin can change role; backend allows role update when current or new role is MM
      if (editingUser.role === 'MM' || editForm.role === 'MM') {
        payload.role = editForm.role;
      }
      const updated = await adminApi.updateUserFull(editingUser.id, payload);
      setUsers(users.map(u => u.id === editingUser.id ? { ...u, ...updated } : u));
      setEditingUser(null);
    } catch (error) {
      console.error('Failed to update user:', error);
    } finally {
      setSavingUser(false);
    }
  };

  const handleDeactivateUser = (user: UserWithEntity) => {
    setDeactivateUser(user);
  };

  const handleCreateEntityForUser = async (user: UserWithEntity) => {
    try {
      const result = await adminApi.createEntityForUser(user.id);
      alert(result.message);
      // Refresh user list to show entity_id
      loadUsers();
    } catch (error) {
      console.error('Failed to create entity:', error);
      alert('Failed to create entity for user');
    }
  };

  const confirmDeactivateUser = async () => {
    if (!deactivateUser) return;

    setDeactivating(true);
    try {
      await adminApi.deleteUser(deactivateUser.id);
      setUsers(users.filter(u => u.id !== deactivateUser.id));
      setPagination(prev => ({ ...prev, total: Math.max(0, prev.total - 1) }));
      if (detailUser?.id === deactivateUser.id) {
        setDetailUser(null);
      }
    } catch (error) {
      console.error('Failed to deactivate user:', error);
    } finally {
      setDeactivating(false);
      setDeactivateUser(null);
    }
  };

  // Bulk operations
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === users.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(users.map(u => u.id)));
    }
  };

  const handleBulkRoleChange = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await adminApi.bulkChangeRole(Array.from(selectedIds), bulkRole);
      setSelectedIds(new Set());
      loadUsers();
    } catch (error) {
      console.error('Bulk role change failed:', error);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkDeactivate = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await adminApi.bulkDeactivate(Array.from(selectedIds));
      setSelectedIds(new Set());
      loadUsers();
    } catch (error) {
      console.error('Bulk deactivate failed:', error);
    } finally {
      setBulkLoading(false);
    }
  };

  // Clear selection when filters/page change
  useEffect(() => {
    setSelectedIds(new Set());
  }, [roleFilter, pagination.page, searchQuery]);

  const openEditModal = (user: UserWithEntity) => {
    setEditingUser(user);
    setEditForm({
      firstName: user.firstName || '',
      lastName: user.lastName || '',
      position: user.position || '',
      role: user.role,
      isActive: user.isActive !== false,
    });
  };

  const openDetailModal = async (userId: string) => {
    setLoadingDetail(true);
    setDetailTab('info');
    try {
      const fullUser = await adminApi.getUserFull(userId);
      setDetailUser(fullUser);
    } catch (error) {
      console.error('Failed to load user details:', error);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handlePasswordReset = async () => {
    if (!detailUser || newPassword.length < 8) return;

    setResettingPassword(true);
    try {
      await adminApi.resetUserPassword(detailUser.id, {
        newPassword: newPassword,
        forceChange: forceChange,
      });
      setShowPasswordReset(false);
      setNewPassword('');
      const updated = await adminApi.getUserFull(detailUser.id);
      setDetailUser(updated);
    } catch (error) {
      console.error('Failed to reset password:', error);
    } finally {
      setResettingPassword(false);
    }
  };

  const loadDeposits = async (entityId: string) => {
    if (!entityId || entityId.trim() === '') {
      console.error('loadDeposits called with invalid entityId:', entityId);
      setDepositsError('Invalid entity ID');
      return;
    }

    setLoadingDeposits(true);
    setDepositsError(null);

    try {
      const [balance, assetsResponse, depositList] = await Promise.all([
        backofficeApi.getEntityBalance(entityId),
        backofficeApi.getEntityAssets(entityId),
        backofficeApi.getDeposits({ entity_id: entityId }),
      ]);

      if (!assetsResponse || typeof assetsResponse !== 'object') {
        throw new Error('Invalid assets response from server');
      }

      setEntityBalance(balance);
      setEntityAssets({
        entityId: assetsResponse.entityId || entityId,
        entityName: assetsResponse.entityName || 'Unknown Entity',
        eurBalance: assetsResponse.eurBalance ?? 0,
        ceaBalance: assetsResponse.ceaBalance ?? 0,
        euaBalance: assetsResponse.euaBalance ?? 0,
      });
      setDeposits(Array.isArray(depositList) ? depositList : []);

      const wireItems: DepositHistoryItem[] = (Array.isArray(depositList) ? depositList : []).map((d) => ({
        type: 'wire_deposit',
        id: d.id,
        amount: d.amount,
        currency: d.currency,
        status: d.status,
        createdAt: d.createdAt,
        wireReference: d.wireReference,
        notes: d.notes,
      }));
      const recentTxs = assetsResponse.recentTransactions ?? [];
      const assetItems: DepositHistoryItem[] = recentTxs.map((t: { id: string; transactionType: string; amount: number; assetType: string; createdAt: string; notes?: string }) => ({
        type: 'asset_tx',
        id: t.id,
        transactionType: t.transactionType === 'WITHDRAWAL' ? 'WITHDRAWAL' : 'DEPOSIT',
        amount: t.amount,
        assetType: t.assetType,
        createdAt: t.createdAt,
        notes: t.notes,
      }));
      const merged = buildDepositAndWithdrawalHistory(wireItems, assetItems);
      setDepositAndWithdrawalHistory(merged);
    } catch (error: unknown) {
      console.error('Failed to load deposits:', error);
      let errorMessage = 'Failed to load entity assets';
      if (error && typeof error === 'object' && 'response' in error) {
        const response = (error as { response?: { status?: number } }).response;
        if (response?.status === 403) {
          errorMessage = 'Access denied - insufficient permissions';
        } else if (response?.status === 404) {
          errorMessage = 'Entity not found';
        }
      } else if (error instanceof Error && error.message?.includes('Network Error')) {
        errorMessage = 'Network error - please check your connection';
      }
      setDepositsError(errorMessage);
      setEntityBalance(null);
      setEntityAssets(null);
      setDeposits([]);
      setDepositAndWithdrawalHistory([]);
    } finally {
      setLoadingDeposits(false);
    }
  };

  const getRoleBadgeVariant = (role: UserRole | 'DISABLED') => {
    switch (role) {
      case 'ADMIN':
        return 'default';
      case 'MM':
        return 'info';
      case 'EUA':
        return 'success';
      case 'NDA':
      case 'KYC':
      case 'APPROVED':
      case 'FUNDING':
      case 'AML':
      case 'CEA':
      case 'CEA_SETTLE':
      case 'SWAP':
      case 'EUA_SETTLE':
        return 'warning';
      case 'REJECTED':
      case 'DISABLED':
        return 'danger';
      default:
        return 'default';
    }
  };

  const getInitials = (firstName?: string, lastName?: string, email?: string) => {
    if (firstName && lastName) {
      return `${firstName[0]}${lastName[0]}`.toUpperCase();
    }
    return email?.substring(0, 2).toUpperCase() || '??';
  };

  if (loading && users.length === 0) {
    return (
      <BackofficeLayout>
        <Card className="mb-6">
          <div className="flex gap-4 mb-4">
            <Skeleton variant="rectangular" height={36} width="40%" />
            <Skeleton variant="rectangular" height={36} width="20%" />
          </div>
        </Card>
        <Card>
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 py-3 border-b border-navy-700 last:border-0">
                <Skeleton variant="circular" width={36} height={36} />
                <div className="flex-1 space-y-1">
                  <Skeleton variant="text" width="30%" />
                  <Skeleton variant="text" width="50%" />
                </div>
                <Skeleton variant="rectangular" width={60} height={22} className="rounded-full" />
                <Skeleton variant="rectangular" width={80} height={22} />
              </div>
            ))}
          </div>
        </Card>
      </BackofficeLayout>
    );
  }

  return (
    <BackofficeLayout
      subSubHeader={
        <Button variant="primary" size="sm" onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4" />
          Create User
        </Button>
      }
    >
      {/* Filters */}
      <Card className="mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-navy-400" />
            <input
              type="text"
              placeholder="Search by name, email, or entity..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-navy-600 bg-navy-800 text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div className="flex gap-2">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value as UserRole | 'all' | 'DISABLED')}
              className="form-select"
            >
              <option value="all">All Roles</option>
              <option value="ADMIN">Admin</option>
              <option value="MM">MM (Market Maker)</option>
              <option value="PREINTRODUCER">Pre-Introducer</option>
              <option value="INTRODUCER">Introducer</option>
              <option value="NDA">NDA</option>
              <option value="KYC">KYC</option>
              <option value="APPROVED">Approved</option>
              <option value="FUNDING">Funding</option>
              <option value="AML">AML</option>
              <option value="REJECTED">Rejected</option>
              <option value="CEA">CEA</option>
              <option value="CEA_SETTLE">CEA Settle</option>
              <option value="SWAP">Swap</option>
              <option value="EUA_SETTLE">EUA Settle</option>
              <option value="EUA">EUA</option>
              <option value="DISABLED">Disabled</option>
            </select>
            <Button variant="ghost" onClick={loadUsers} disabled={loading}>
              <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
            </Button>
          </div>
        </div>
      </Card>

      {/* Users Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-navy-700">
                <th className="py-4 px-2 w-10">
                  <input
                    type="checkbox"
                    checked={users.length > 0 && selectedIds.size === users.length}
                    onChange={toggleSelectAll}
                    className="rounded border-navy-600 bg-navy-800 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-0"
                  />
                </th>
                <th className="text-left py-4 px-4 text-xs font-medium text-navy-400 uppercase tracking-wider">
                  User
                </th>
                <th className="text-left py-4 px-4 text-xs font-medium text-navy-400 uppercase tracking-wider">
                  Entity
                </th>
                <th className="text-left py-4 px-4 text-xs font-medium text-navy-400 uppercase tracking-wider">
                  Role
                </th>
                <th className="text-left py-4 px-4 text-xs font-medium text-navy-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="text-left py-4 px-4 text-xs font-medium text-navy-400 uppercase tracking-wider">
                  Last Activity
                </th>
                <th className="text-right py-4 px-4 text-xs font-medium text-navy-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-700">
              {users.map((user, index) => (
                <motion.tr
                  key={user.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={cn("hover:bg-navy-800/50", selectedIds.has(user.id) && "bg-emerald-500/5")}
                >
                  <td className="py-4 px-2 w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(user.id)}
                      onChange={() => toggleSelect(user.id)}
                      className="rounded border-navy-600 bg-navy-800 text-emerald-500 focus:ring-emerald-500 focus:ring-offset-0"
                    />
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm',
                          user.role === 'ADMIN'
                            ? 'bg-gradient-to-br from-navy-500 to-navy-600'
                            : user.role === 'MM'
                              ? 'bg-gradient-to-br from-blue-500 to-blue-600'
                              : 'bg-gradient-to-br from-amber-500 to-amber-600'
                        )}
                      >
                        {getInitials(user.firstName, user.lastName, user.email)}
                      </div>
                      <div>
                        <p className="font-medium text-white">
                          {user.firstName && user.lastName
                            ? `${user.firstName} ${user.lastName}`
                            : 'Name not set'}
                        </p>
                        <p className="text-sm text-navy-400">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      <Building2 className="w-4 h-4 text-navy-400" />
                      <span className="text-sm text-navy-300">
                        {user.entityName || 'No entity'}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <div className="relative">
                      {user.isActive === false ? (
                        <Badge variant={getRoleBadgeVariant('DISABLED')}>
                          DISABLED
                        </Badge>
                      ) : (
                        <Badge variant={getRoleBadgeVariant(user.role)}>
                          {(user.role ?? (user as unknown as Record<string, unknown>).role as string)?.toUpperCase() ?? '—'}
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <Badge variant={user.isActive !== false ? 'success' : 'danger'}>
                      {user.isActive !== false ? 'Active' : 'DISABLED'}
                    </Badge>
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-navy-400" />
                      <span className="text-sm text-navy-300">
                        {user.lastLogin
                            ? formatRelativeTime(user.lastLogin)
                            : 'Never'}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openDetailModal(user.id)}
                        title="View Details"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditModal(user)}
                        title="Edit"
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                      {user.entityId ? (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setAddAssetUser({
                              id: user.id,
                              entityId: user.entityId!,
                              entityName: user.entityName || 'Unknown Entity'
                            })}
                            className="text-emerald-500 hover:text-emerald-600 hover:bg-emerald-900/20"
                            title="Add Asset"
                          >
                            <Plus className="w-4 h-4" />
                          </Button>
                        </>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCreateEntityForUser(user)}
                          className="text-amber-500 hover:text-amber-600 hover:bg-amber-900/20"
                          title="Create Entity (required for deposits)"
                        >
                          <Building2 className="w-4 h-4" />
                        </Button>
                      )}
                      {user.isActive !== false && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeactivateUser(user)}
                          className="text-red-500 hover:text-red-600 hover:bg-red-900/20"
                          title="Deactivate"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        {users.length === 0 && !loading && (
          <div className="text-center py-12">
            <Users className="w-12 h-12 text-navy-600 mx-auto mb-4" />
            <p className="text-navy-400">No users found matching your criteria</p>
          </div>
        )}

        {/* Pagination */}
        {pagination.totalPages > 1 && (
          <div className="flex justify-center gap-2 mt-6 pt-6 border-t border-navy-700">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
              disabled={pagination.page === 1}
            >
              Previous
            </Button>
            <span className="px-4 py-2 text-sm text-navy-300">
              Page {pagination.page} of {pagination.totalPages}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
              disabled={pagination.page === pagination.totalPages}
            >
              Next
            </Button>
          </div>
        )}
      </Card>

      {/* Bulk Action Bar */}
      <AnimatePresence>
        {selectedIds.size > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-xl bg-navy-800 border border-navy-600 shadow-2xl shadow-black/40"
          >
            <div className="flex items-center gap-2 text-sm text-navy-300 mr-2">
              <CheckSquare className="w-4 h-4 text-emerald-400" />
              <span className="font-medium text-white">{selectedIds.size}</span> selected
            </div>
            <div className="w-px h-6 bg-navy-600" />
            <select
              value={bulkRole}
              onChange={(e) => setBulkRole(e.target.value as UserRole)}
              className="form-select text-sm py-1.5 bg-navy-700 border-navy-600"
            >
              <option value="NDA">NDA</option>
              <option value="KYC">KYC</option>
              <option value="APPROVED">Approved</option>
              <option value="FUNDING">Funding</option>
              <option value="AML">AML</option>
              <option value="CEA">CEA</option>
              <option value="CEA_SETTLE">CEA Settle</option>
              <option value="SWAP">Swap</option>
              <option value="EUA_SETTLE">EUA Settle</option>
              <option value="EUA">EUA</option>
            </select>
            <Button variant="primary" size="sm" onClick={handleBulkRoleChange} disabled={bulkLoading}>
              Change Role
            </Button>
            <div className="w-px h-6 bg-navy-600" />
            <Button
              variant="ghost"
              size="sm"
              onClick={handleBulkDeactivate}
              disabled={bulkLoading}
              className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
            >
              <ShieldAlert className="w-4 h-4 mr-1" />
              Deactivate
            </Button>
            <button
              onClick={() => setSelectedIds(new Set())}
              className="ml-1 p-1 rounded hover:bg-navy-700 text-navy-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create User Modal */}
      <CreateUserModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        newUser={newUser}
        setNewUser={setNewUser}
        useInvitation={useInvitation}
        setUseInvitation={setUseInvitation}
        onSubmit={handleCreateUser}
        saving={savingUser}
      />

      {/* Edit User Modal */}
      <EditUserModal
        user={editingUser}
        onClose={() => setEditingUser(null)}
        editForm={editForm}
        setEditForm={setEditForm}
        onSubmit={handleUpdateUser}
        saving={savingUser}
      />

      {/* User Detail Modal */}
      <UserDetailModal
        user={detailUser}
        loading={loadingDetail}
        onClose={() => setDetailUser(null)}
        activeTab={detailTab}
        setActiveTab={setDetailTab}
        onLoadDeposits={loadDeposits}
        onShowPasswordReset={() => setShowPasswordReset(true)}
        onEditAsset={setEditingAsset}
        loadingDeposits={loadingDeposits}
        depositsError={depositsError}
        entityBalance={entityBalance}
        entityAssets={entityAssets}
        deposits={deposits}
        depositAndWithdrawalHistory={depositAndWithdrawalHistory}
      />

      {/* Password Reset Modal */}
      <PasswordResetModal
        isOpen={showPasswordReset && !!detailUser}
        onClose={() => setShowPasswordReset(false)}
        userEmail={detailUser?.email || ''}
        newPassword={newPassword}
        setNewPassword={setNewPassword}
        forceChange={forceChange}
        setForceChange={setForceChange}
        onSubmit={handlePasswordReset}
        resetting={resettingPassword}
      />

      {/* Deactivate User Confirmation Modal */}
      <ConfirmationModal
        isOpen={!!deactivateUser}
        onClose={() => setDeactivateUser(null)}
        onConfirm={confirmDeactivateUser}
        title="Deactivate User"
        message="This will deactivate the user account. The user will no longer be able to log in. This action can be reversed by reactivating the account."
        confirmText="Deactivate User"
        cancelText="Cancel"
        variant="warning"
        requireConfirmation={deactivateUser?.email?.split('@')[0]}
        details={deactivateUser ? [
          { label: 'Email', value: deactivateUser.email },
          { label: 'Name', value: `${deactivateUser.firstName || ''} ${deactivateUser.lastName || ''}`.trim() || 'N/A' },
          { label: 'Role', value: deactivateUser.role },
          { label: 'Company', value: deactivateUser.entityName || 'N/A' },
        ] : []}
        loading={deactivating}
      />

      {/* Add Asset Modal */}
      {addAssetUser && (
        <AddAssetModal
          isOpen={!!addAssetUser}
          onClose={() => setAddAssetUser(null)}
          onSuccess={() => {
            if (detailUser?.entityId === addAssetUser.entityId) {
              loadDeposits(addAssetUser.entityId);
            }
            loadUsers();
          }}
          entityId={addAssetUser.entityId}
          entityName={addAssetUser.entityName}
        />
      )}

      {/* Edit Asset Modal */}
      {editingAsset && (
        <EditAssetModal
          isOpen={!!editingAsset}
          onClose={() => setEditingAsset(null)}
          onSuccess={() => {
            if (detailUser?.entityId) {
              loadDeposits(detailUser.entityId);
            }
          }}
          entityId={editingAsset.entityId}
          entityName={editingAsset.entityName}
          assetType={editingAsset.assetType}
          currentBalance={editingAsset.currentBalance}
        />
      )}
    </BackofficeLayout>
  );
}
