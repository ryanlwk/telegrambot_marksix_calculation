#!/usr/bin/env python
"""
Live Prediction Tracker
記錄每次預測並在開獎後更新實際結果，用於追蹤真實世界的準確率
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import pandas as pd


class PredictionTracker:
    """預測追蹤器 - 記錄和驗證預測結果"""
    
    def __init__(self, tracker_file: str = "live_predictions.csv"):
        """
        初始化追蹤器
        
        Args:
            tracker_file: 追蹤檔案路徑
        """
        self.tracker_file = Path(tracker_file)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """確保追蹤檔案存在，如不存在則建立"""
        if not self.tracker_file.exists():
            with open(self.tracker_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'prediction_id',
                    'timestamp',
                    'expected_draw_date',
                    'algorithm',
                    'predicted_numbers',
                    'actual_numbers',
                    'matches',
                    'user_id',
                    'status'  # pending, matched, expired
                ])
    
    def log_prediction(
        self,
        predicted_numbers: List[int],
        expected_draw_date: str,
        algorithm: str = "ensemble",
        user_id: Optional[str] = None
    ) -> str:
        """
        記錄一次預測
        
        Args:
            predicted_numbers: 預測的 6 個號碼
            expected_draw_date: 預期開獎日期 (YYYY-MM-DD)
            algorithm: 使用的算法
            user_id: 用戶 ID（可選）
        
        Returns:
            預測 ID
        """
        timestamp = datetime.now().isoformat()
        prediction_id = f"pred_{timestamp.replace(':', '').replace('-', '').replace('.', '')}"
        
        with open(self.tracker_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                prediction_id,
                timestamp,
                expected_draw_date,
                algorithm,
                ','.join(map(str, sorted(predicted_numbers))),
                '',  # actual_numbers (待填入)
                '',  # matches (待計算)
                user_id or '',
                'pending'
            ])
        
        return prediction_id
    
    def update_with_actual(
        self,
        draw_date: str,
        actual_numbers: List[int]
    ) -> int:
        """
        更新指定日期的預測結果
        
        Args:
            draw_date: 開獎日期 (YYYY-MM-DD)
            actual_numbers: 實際開獎號碼
        
        Returns:
            更新的記錄數量
        """
        df = pd.read_csv(self.tracker_file)
        
        # 找出該日期的待處理預測
        mask = (df['expected_draw_date'] == draw_date) & (df['status'] == 'pending')
        
        if not mask.any():
            return 0
        
        updated_count = 0
        
        for idx in df[mask].index:
            # 計算命中數
            predicted = [int(x) for x in df.loc[idx, 'predicted_numbers'].split(',')]
            matches = len(set(predicted) & set(actual_numbers))
            
            # 更新記錄
            df.loc[idx, 'actual_numbers'] = ','.join(map(str, sorted(actual_numbers)))
            df.loc[idx, 'matches'] = matches
            df.loc[idx, 'status'] = 'matched'
            
            updated_count += 1
        
        # 寫回檔案
        df.to_csv(self.tracker_file, index=False, encoding='utf-8')
        
        return updated_count
    
    def get_statistics(self, algorithm: Optional[str] = None) -> dict:
        """
        取得統計數據
        
        Args:
            algorithm: 篩選特定算法（可選）
        
        Returns:
            統計數據字典
        """
        df = pd.read_csv(self.tracker_file)
        
        # 只統計已配對的預測
        matched_df = df[df['status'] == 'matched']
        
        if algorithm:
            matched_df = matched_df[matched_df['algorithm'] == algorithm]
        
        if len(matched_df) == 0:
            return {
                'total_predictions': 0,
                'average_matches': 0,
                'match_distribution': {}
            }
        
        # 計算統計
        matches_list = matched_df['matches'].tolist()
        
        from collections import Counter
        match_dist = Counter(matches_list)
        
        stats = {
            'total_predictions': len(matched_df),
            'pending_predictions': len(df[df['status'] == 'pending']),
            'average_matches': sum(matches_list) / len(matches_list),
            'match_distribution': dict(match_dist),
            'best_prediction': matched_df.loc[matched_df['matches'].idxmax()].to_dict() if len(matched_df) > 0 else None
        }
        
        return stats
    
    def print_statistics(self, algorithm: Optional[str] = None):
        """
        列印統計報告
        
        Args:
            algorithm: 篩選特定算法（可選）
        """
        stats = self.get_statistics(algorithm)
        
        if stats['total_predictions'] == 0:
            print("📊 尚無已驗證的預測記錄")
            return
        
        algo_text = f" ({algorithm})" if algorithm else ""
        
        print(f"\n{'='*60}")
        print(f"📊 真實世界預測統計{algo_text}")
        print(f"{'='*60}")
        
        print(f"\n📈 基本統計:")
        print(f"   • 已驗證預測: {stats['total_predictions']} 次")
        print(f"   • 待驗證預測: {stats['pending_predictions']} 次")
        print(f"   • 平均命中數: {stats['average_matches']:.3f} / 6")
        
        print(f"\n🎯 命中分佈:")
        for matches in range(7):
            count = stats['match_distribution'].get(matches, 0)
            if stats['total_predictions'] > 0:
                percentage = count / stats['total_predictions'] * 100
                bar = "█" * int(percentage / 2)
                print(f"   {matches}/6 命中: {count:3d} 次 ({percentage:5.1f}%) {bar}")
        
        if stats['best_prediction']:
            best = stats['best_prediction']
            print(f"\n🏆 最佳預測:")
            print(f"   日期: {best['expected_draw_date']}")
            print(f"   預測: {best['predicted_numbers']}")
            print(f"   實際: {best['actual_numbers']}")
            print(f"   命中: {best['matches']}/6")
        
        print(f"{'='*60}\n")
    
    def mark_expired(self, cutoff_date: str) -> int:
        """
        標記過期的預測（超過指定日期仍未更新）
        
        Args:
            cutoff_date: 截止日期 (YYYY-MM-DD)
        
        Returns:
            標記為過期的數量
        """
        df = pd.read_csv(self.tracker_file)
        
        mask = (df['expected_draw_date'] < cutoff_date) & (df['status'] == 'pending')
        expired_count = mask.sum()
        
        if expired_count > 0:
            df.loc[mask, 'status'] = 'expired'
            df.to_csv(self.tracker_file, index=False, encoding='utf-8')
        
        return expired_count


# ==================== 真實權重計算 ====================
def compute_live_weights(tracker_file: str = "live_predictions.csv") -> Optional[dict]:
    """
    從真實預測記錄計算算法權重
    
    只有當累積 30 筆以上已驗證的預測時才返回權重
    否則返回 None（數據不足，應使用預設回測權重）
    
    Args:
        tracker_file: 追蹤檔案路徑
    
    Returns:
        權重字典 (1-5 scale)，如果數據不足則返回 None
    """
    from pathlib import Path
    
    if not Path(tracker_file).exists():
        return None
    
    df = pd.read_csv(tracker_file)
    
    # 只統計已驗證的預測
    matched = df[df['status'] == 'matched']
    
    if len(matched) < 30:
        return None  # 數據不足，需要至少 30 筆
    
    # 計算每個算法的平均命中數
    algo_performance = {}
    for algo in matched['algorithm'].unique():
        algo_data = matched[matched['algorithm'] == algo]
        if len(algo_data) > 0:
            avg_matches = algo_data['matches'].mean()
            algo_performance[algo] = avg_matches
    
    if not algo_performance:
        return None
    
    # 轉換為 1-5 權重（最差=1, 最好=5）
    min_perf = min(algo_performance.values())
    max_perf = max(algo_performance.values())
    
    if max_perf == min_perf:
        # 所有算法表現相同，給予相同權重
        return {algo: 3 for algo in algo_performance}
    
    weights = {}
    for algo, perf in algo_performance.items():
        # 線性縮放到 1-5 範圍
        normalized = (perf - min_perf) / (max_perf - min_perf)
        weights[algo] = max(1, min(5, int(1 + normalized * 4)))
    
    return weights


# ==================== 便捷函數 ====================
def track_prediction(
    predicted_numbers: List[int],
    expected_draw_date: str,
    algorithm: str = "ensemble",
    user_id: Optional[str] = None
) -> str:
    """
    快速記錄預測（便捷函數）
    
    Args:
        predicted_numbers: 預測號碼
        expected_draw_date: 預期開獎日期
        algorithm: 算法名稱
        user_id: 用戶 ID
    
    Returns:
        預測 ID
    """
    tracker = PredictionTracker()
    return tracker.log_prediction(predicted_numbers, expected_draw_date, algorithm, user_id)


def update_results(draw_date: str, actual_numbers: List[int]) -> int:
    """
    更新開獎結果（便捷函數）
    
    Args:
        draw_date: 開獎日期
        actual_numbers: 實際號碼
    
    Returns:
        更新數量
    """
    tracker = PredictionTracker()
    return tracker.update_with_actual(draw_date, actual_numbers)


def show_stats(algorithm: Optional[str] = None):
    """
    顯示統計（便捷函數）
    
    Args:
        algorithm: 算法名稱（可選）
    """
    tracker = PredictionTracker()
    tracker.print_statistics(algorithm)


if __name__ == "__main__":
    # 測試追蹤器
    print("🔍 Prediction Tracker 測試\n")
    
    tracker = PredictionTracker()
    
    # 模擬記錄預測
    pred_id = tracker.log_prediction(
        predicted_numbers=[5, 12, 23, 28, 37, 44],
        expected_draw_date="2026-03-14",
        algorithm="ensemble",
        user_id="test_user"
    )
    print(f"✅ 已記錄預測: {pred_id}")
    
    # 顯示統計
    tracker.print_statistics()
    
    print("💡 使用範例:")
    print("   1. 預測時: track_prediction([1,2,3,4,5,6], '2026-03-14', 'ensemble')")
    print("   2. 開獎後: update_results('2026-03-14', [3,7,12,25,38,41])")
    print("   3. 查看統計: show_stats()")
