#!/usr/bin/env python
"""
Mark Six 預測引擎
提供多種預測算法和統計分析功能
"""

import random
import pandas as pd
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Tuple, Dict


class MarkSixEngine:
    """Mark Six 預測引擎核心類別"""
    
    # 算法權重（基於 28 期回測結果）
    ALGO_WEIGHTS = {
        'recency_weighted': 3,    # +14.9%
        'cold_number': 2,         # +5.4%
        'pair_weighted': 2,       # +0.6%
        'smart_hybrid': 1,        # -18.6%
        'gap_weighted': 1,        # -9.0%
        'weighted_frequency': 1,  # -18.6%
    }
    
    def __init__(self, history_data: List[List[int]] = None, csv_path: str = None):
        """
        初始化預測引擎
        
        Args:
            history_data: 歷史開獎數據列表 [[n1, n2, n3, n4, n5, n6], ...]
            csv_path: CSV 檔案路徑（如果未提供 history_data）
        """
        # 設定 CSV 路徑
        if csv_path:
            self.csv_path = csv_path
        else:
            default_path = Path(__file__).parent / "history.csv"
            self.csv_path = str(default_path)
        
        # 載入歷史數據
        if history_data is not None:
            self.history = history_data
        else:
            self.history = self._load_from_csv(self.csv_path)
        
        # 展平所有號碼以計算頻率
        self.flat_list = [num for draw in self.history for num in draw]
        self.frequency = Counter(self.flat_list)
        
        # 建立配對矩陣（用於配對加成）
        self.pair_matrix = self._build_pair_matrix(self.history)
        
        # 尋找最佳視窗大小（實驗性功能，可能影響效能）
        # self.optimal_window = self._find_optimal_window()
        
        # 嘗試從真實預測記錄載入權重
        self._load_live_weights()
    
    def _load_from_csv(self, csv_path: str, window_size: int = None) -> List[List[int]]:
        """
        從 CSV 載入歷史數據
        
        Args:
            csv_path: CSV 檔案路徑
            window_size: 載入最近 N 期數據（None = 自動優化）
        
        Returns:
            歷史數據列表
        """
        df = pd.read_csv(csv_path)
        
        # 如果未指定視窗大小，先載入全部用於優化
        if window_size is None:
            # 載入全部數據用於視窗優化
            history_data = df[['n1', 'n2', 'n3', 'n4', 'n5', 'n6']].values.tolist()
        else:
            # 只取最近 window_size 期的 6 個主要號碼（不含 special_number）
            history_data = df[['n1', 'n2', 'n3', 'n4', 'n5', 'n6']].head(window_size).values.tolist()
        
        return history_data
    
    def _find_optimal_window(self, test_sizes: List[int] = [20, 30, 40, 50]) -> int:
        """
        尋找最佳視窗大小
        
        測試多個視窗大小，返回平均命中數最高的視窗
        
        Args:
            test_sizes: 要測試的視窗大小列表
        
        Returns:
            最佳視窗大小
        """
        # 載入完整歷史數據
        df = pd.read_csv(self.csv_path)
        full_history = df[['n1', 'n2', 'n3', 'n4', 'n5', 'n6']].values.tolist()
        
        if len(full_history) < max(test_sizes) + 10:
            # 數據不足，返回預設值
            return 30
        
        results = {}
        
        for size in test_sizes:
            if len(full_history) < size + 10:
                continue
            
            scores = []
            # 測試接下來的 10-20 期
            test_range = min(20, len(full_history) - size)
            
            for test_idx in range(size, size + test_range):
                train = full_history[:test_idx]
                actual = set(full_history[test_idx])
                
                # 使用時間衰減算法測試（最穩定的單一算法）
                temp_engine = MarkSixEngine(history_data=train, csv_path=self.csv_path)
                pred, _ = temp_engine.predict_recency_weighted(max_attempts=500)
                
                matches = len(set(pred) & actual)
                scores.append(matches)
            
            if scores:
                results[size] = sum(scores) / len(scores)
        
        if not results:
            return 30  # 預設值
        
        optimal = max(results, key=results.get)
        print(f"🔍 視窗優化結果: {results}")
        print(f"✅ 最佳視窗大小: {optimal}")
        
        return optimal
    
    def _load_live_weights(self):
        """從真實預測記錄載入算法權重"""
        try:
            from prediction_tracker import compute_live_weights
            live_weights = compute_live_weights()
            
            if live_weights is not None:
                print(f"✅ 使用真實預測權重: {live_weights}")
                self.ALGO_WEIGHTS = live_weights
            else:
                print(f"ℹ️  使用預設回測權重（真實數據不足 30 筆）")
        except Exception as e:
            print(f"⚠️  無法載入真實權重，使用預設值: {e}")
    
    def get_stats(self, top_n: int = 5) -> List[Tuple[int, int]]:
        """
        取得最熱門號碼統計
        
        Args:
            top_n: 返回前 N 個最常出現的號碼
        
        Returns:
            [(號碼, 出現次數), ...] 列表
        """
        return self.frequency.most_common(top_n)
    
    def _validate(self, numbers: List[int]) -> bool:
        """
        驗證號碼組合是否符合現實條件
        
        檢查項目:
        1. 總和範圍: 91-230
        2. 奇偶比: 2:4, 3:3, 或 4:2
        3. 連續號碼: 最多 2 個連續
        
        Args:
            numbers: 待驗證的 6 個號碼
        
        Returns:
            True 如果通過驗證，否則 False
        """
        nums = sorted(numbers)
        
        # 1. 總和檢查（歷史上最常見的範圍）
        s = sum(nums)
        if not (91 <= s <= 230):
            return False
        
        # 2. 奇偶比檢查
        odds = len([n for n in nums if n % 2 != 0])
        if odds not in [2, 3, 4]:
            return False
        
        # 3. 連續號碼檢查（最多 2 個連續，即不允許 3 個連號）
        consecutive_streak = 0
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                consecutive_streak += 1
            else:
                consecutive_streak = 0
            if consecutive_streak >= 2:  # 3 個連號
                return False
        
        return True
    
    def _avoid_recent_patterns(self, numbers: List[int], lookback: int = 10) -> bool:
        """
        避免選擇與最近開獎過於相似的組合
        
        Args:
            numbers: 候選號碼
            lookback: 檢查最近 N 期
        
        Returns:
            True 如果組合夠新穎，否則 False
        """
        recent_draws = self.history[:lookback]
        
        for recent_draw in recent_draws:
            overlap = len(set(numbers) & set(recent_draw))
            # 如果與最近某期重疊 >= 4 個號碼，拒絕
            if overlap >= 4:
                return False
        
        return True
    
    # ==================== 算法 1: 加權頻率 ====================
    def predict_weighted_frequency(self, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 1: 基於頻率的加權隨機抽樣
        
        出現越頻繁的號碼，被選中的機率越高
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        population = list(range(1, 50))
        weights = [self.frequency.get(i, 1) for i in population]
        
        for _ in range(max_attempts):
            sample = random.choices(population, weights=weights, k=10)
            unique_sample = sorted(list(set(sample)))
            
            if len(unique_sample) >= 6:
                final_selection = random.sample(unique_sample, 6)
                if self._validate(final_selection):
                    return sorted(final_selection), False
        
        # Fallback: 純隨機
        return sorted(random.sample(population, 6)), True
    
    # ==================== 算法 2: 時間衰減加權（改進版）====================
    def predict_recency_weighted(self, decay_factor: float = 0.95, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 2: 時間衰減加權 + 配對共現加成 + 開獎日偏好
        
        最近的開獎結果權重更高，隨時間遞減
        額外考慮：
        1. 配對共現：與最近號碼經常一起出現的號碼加成（最多 +20%）
        2. 開獎日偏好：特定星期的號碼頻率加成（最多 +10%）
        
        Args:
            decay_factor: 衰減係數 (0.9=快速衰減, 0.99=慢速衰減)
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        weights_dict = {}
        
        # 1. 基礎時間衰減權重
        for draw_idx, draw in enumerate(self.history):
            weight = decay_factor ** (len(self.history) - draw_idx - 1)
            for num in draw:
                weights_dict[num] = weights_dict.get(num, 0) + weight
        
        # 2. 配對共現加成（最多 +20%）
        recent_numbers = set()
        for draw in self.history[:5]:  # 最近 5 期
            recent_numbers.update(draw)
        
        pair_boost = {}
        for num in range(1, 50):
            boost = 0
            for recent_num in recent_numbers:
                pair_key = tuple(sorted([num, recent_num]))
                if pair_key in self.pair_matrix:
                    boost += self.pair_matrix[pair_key]
            pair_boost[num] = boost
        
        # 正規化配對加成到 0-0.2 範圍
        max_boost = max(pair_boost.values()) if pair_boost else 1
        if max_boost > 0:
            for num in pair_boost:
                pair_boost[num] = (pair_boost[num] / max_boost) * 0.2
        
        # 3. 開獎日偏好加成（最多 +10%）
        next_weekday = self._get_next_draw_weekday()
        day_freq = self._get_draw_day_frequency(next_weekday)
        
        day_boost = {}
        max_day_freq = max(day_freq.values()) if day_freq else 1
        for num in range(1, 50):
            if num in day_freq and max_day_freq > 0:
                day_boost[num] = (day_freq[num] / max_day_freq) * 0.1
            else:
                day_boost[num] = 0
        
        # 4. 組合所有權重：基礎 × (1 + 配對加成 + 開獎日加成)
        for num in weights_dict:
            weights_dict[num] = weights_dict[num] * (1 + pair_boost.get(num, 0) + day_boost.get(num, 0))
        
        population = list(range(1, 50))
        weights = [weights_dict.get(i, 0.1) for i in population]
        
        for _ in range(max_attempts):
            sample = random.choices(population, weights=weights, k=10)
            unique_sample = sorted(list(set(sample)))
            
            if len(unique_sample) >= 6:
                final_selection = random.sample(unique_sample, 6)
                if self._validate(final_selection):
                    return sorted(final_selection), False
        
        return sorted(random.sample(population, 6)), True
    
    # ==================== 算法 3: 冷號回歸 ====================
    def predict_cold_number_boost(self, boost_factor: float = 1.5, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 3: 冷號回歸理論
        
        長期未出現的號碼給予額外權重
        
        Args:
            boost_factor: 冷號加權係數
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        # 計算每個號碼最後一次出現的位置
        last_seen = {}
        for draw_idx, draw in enumerate(self.history):
            for num in draw:
                last_seen[num] = draw_idx
        
        # 計算「冷度」權重
        weights_dict = {}
        latest_draw = len(self.history) - 1
        
        for num in range(1, 50):
            if num not in last_seen:
                # 從未出現 = 超冷
                weights_dict[num] = boost_factor * 2
            else:
                # 距離越遠 = 越冷 = 權重越高
                draws_since = latest_draw - last_seen[num]
                weights_dict[num] = 1 + (draws_since / len(self.history)) * boost_factor
        
        population = list(range(1, 50))
        weights = [weights_dict[i] for i in population]
        
        for _ in range(max_attempts):
            sample = random.choices(population, weights=weights, k=10)
            unique_sample = sorted(list(set(sample)))
            
            if len(unique_sample) >= 6:
                final_selection = random.sample(unique_sample, 6)
                if self._validate(final_selection):
                    return sorted(final_selection), False
        
        return sorted(random.sample(population, 6)), True
    
    # ==================== 算法 4: 智能混合（推薦）====================
    def predict_smart_hybrid(self, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 4: 智能混合策略（推薦使用）
        
        結合時間衰減加權 (50%) + 冷號回歸 (30%) + 均勻分佈 (20%)
        並套用模式避免過濾器
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        # 1. 計算時間衰減權重
        recency_weights = {}
        for draw_idx, draw in enumerate(self.history):
            weight = 0.95 ** (len(self.history) - draw_idx - 1)
            for num in draw:
                recency_weights[num] = recency_weights.get(num, 0) + weight
        
        # 2. 計算冷號權重
        last_seen = {}
        for draw_idx, draw in enumerate(self.history):
            for num in draw:
                last_seen[num] = draw_idx
        
        cold_weights = {}
        latest_draw = len(self.history) - 1
        for num in range(1, 50):
            if num not in last_seen:
                cold_weights[num] = 3.0
            else:
                draws_since = latest_draw - last_seen[num]
                cold_weights[num] = 1 + (draws_since / len(self.history)) * 1.3
        
        # 3. 組合權重 (50% 時間衰減 + 30% 冷號 + 20% 均勻)
        combined_weights = {}
        for num in range(1, 50):
            combined_weights[num] = (
                0.5 * recency_weights.get(num, 0.1) +
                0.3 * cold_weights.get(num, 1.0) +
                0.2 * 1.0
            )
        
        population = list(range(1, 50))
        weights = [combined_weights[i] for i in population]
        
        # 4. 生成候選並套用雙重過濾
        for _ in range(max_attempts):
            sample = random.choices(population, weights=weights, k=10)
            unique_sample = sorted(list(set(sample)))
            
            if len(unique_sample) >= 6:
                candidate = random.sample(unique_sample, 6)
                
                # 雙重過濾: 基本驗證 + 模式避免
                if self._validate(candidate) and self._avoid_recent_patterns(candidate):
                    return sorted(candidate), False
        
        return sorted(random.sample(population, 6)), True
    
    # ==================== 算法 5: 配對頻率（Co-occurrence）====================
    def _build_pair_matrix(self, history_data: List[List[int]]) -> Dict[Tuple[int, int], int]:
        """
        建立配對矩陣：統計哪些號碼經常一起出現
        
        Args:
            history_data: 歷史開獎數據
        
        Returns:
            配對計數字典 {(num1, num2): count}
        """
        pair_counts = defaultdict(int)
        
        for draw in history_data:
            # 對每一期的號碼，計算所有配對組合
            for i in range(len(draw)):
                for j in range(i + 1, len(draw)):
                    # 確保配對順序一致（小號在前）
                    pair = tuple(sorted([draw[i], draw[j]]))
                    pair_counts[pair] += 1
        
        return dict(pair_counts)
    
    def _get_draw_day_frequency(self, target_weekday: int) -> Dict[int, int]:
        """
        取得特定星期幾的號碼頻率
        
        Args:
            target_weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
        
        Returns:
            號碼頻率字典
        """
        df = pd.read_csv(self.csv_path)
        df['date'] = pd.to_datetime(df['date'])
        df['weekday'] = df['date'].dt.dayofweek
        
        # 篩選目標星期
        day_draws = df[df['weekday'] == target_weekday]
        
        # 計算頻率
        freq = {}
        for _, row in day_draws.iterrows():
            for num in [row['n1'], row['n2'], row['n3'], row['n4'], row['n5'], row['n6']]:
                freq[num] = freq.get(num, 0) + 1
        
        return freq
    
    def _get_next_draw_weekday(self) -> int:
        """
        預測下次開獎是星期幾
        
        Mark Six 開獎日：週二(1)、週四(3)、週六(5)
        
        Returns:
            下次開獎的星期幾 (0=Mon, 1=Tue, ..., 6=Sun)
        """
        from datetime import datetime, timedelta
        
        today = datetime.now()
        weekday = today.weekday()
        
        # 根據今天是星期幾，推算下次開獎日
        if weekday in [0, 1]:  # 週一、週二
            return 3  # 下次是週四
        elif weekday in [2, 3]:  # 週三、週四
            return 5  # 下次是週六
        else:  # 週五、週六、週日
            return 1  # 下次是週二
    
    def _momentum_score(self, lookback: int = 10) -> Dict[int, int]:
        """
        檢測熱勢號碼（連續出現的號碼）
        
        在最近 N 期中出現 3 次以上的號碼視為「熱勢中」
        
        Args:
            lookback: 檢查最近 N 期
        
        Returns:
            {號碼: 出現次數} 字典（只包含 3+ 次的號碼）
        """
        recent = self.history[:lookback]
        counts = Counter()
        
        for draw in recent:
            counts.update(draw)
        
        # 只返回出現 3 次以上的號碼（熱勢中）
        return {num: count for num, count in counts.items() if count >= 3}
    
    def _consecutive_penalty(self, numbers: List[int]) -> int:
        """
        計算連號懲罰分數
        
        連續號碼對（如 5,6 或 31,32）在實際開獎中較少出現
        
        Args:
            numbers: 號碼列表
        
        Returns:
            連號對數量（越高表示越多連號）
        """
        sorted_nums = sorted(numbers)
        penalty = 0
        
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i+1] - sorted_nums[i] == 1:
                penalty += 1
        
        return penalty
    
    def _balance_prediction(self, numbers: List[int], scores: Dict[int, float] = None) -> List[int]:
        """
        平衡預測號碼的範圍分佈
        
        確保預測涵蓋至少 2 個號碼區段：
        - 低段: 1-16
        - 中段: 17-32
        - 高段: 33-49
        
        Args:
            numbers: 原始預測號碼
            scores: 號碼分數字典（用於替換時選擇）
        
        Returns:
            平衡後的號碼列表
        """
        low = [n for n in numbers if n <= 16]
        mid = [n for n in numbers if 17 <= n <= 32]
        high = [n for n in numbers if n >= 33]
        
        bands_covered = sum([bool(low), bool(mid), bool(high)])
        
        # 如果已涵蓋 2+ 個區段，不需調整
        if bands_covered >= 2:
            return numbers
        
        # 需要調整：從其他區段選擇號碼
        if scores is None:
            # 沒有分數資訊，無法智能替換，返回原始預測
            return numbers
        
        # 找出缺少的區段
        missing_bands = []
        if not low:
            missing_bands.append((1, 16))
        if not mid:
            missing_bands.append((17, 32))
        if not high:
            missing_bands.append((33, 49))
        
        # 從缺少的區段中選擇高分號碼
        result = numbers.copy()
        
        for band_min, band_max in missing_bands[:2]:  # 最多替換 2 個
            # 找出該區段中分數最高的號碼
            band_candidates = {n: s for n, s in scores.items() 
                             if band_min <= n <= band_max and n not in result}
            
            if band_candidates:
                best_in_band = max(band_candidates, key=band_candidates.get)
                # 替換分數最低的號碼
                worst_in_result = min(result, key=lambda n: scores.get(n, 0))
                result.remove(worst_in_result)
                result.append(best_in_band)
        
        return sorted(result)
    
    def predict_pair_weighted(self, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 5: 基於配對頻率的預測
        
        統計哪些號碼經常一起出現，並給予這些號碼更高的權重
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        # 建立配對矩陣
        pair_matrix = self._build_pair_matrix(self.history)
        
        # 計算每個號碼的配對分數（與其他號碼一起出現的總次數）
        scores = defaultdict(int)
        for (num1, num2), count in pair_matrix.items():
            scores[num1] += count
            scores[num2] += count
        
        # 確保所有號碼都有分數
        population = list(range(1, 50))
        weights = [scores.get(i, 1) for i in population]
        
        for _ in range(max_attempts):
            sample = random.choices(population, weights=weights, k=10)
            unique_sample = sorted(list(set(sample)))
            
            if len(unique_sample) >= 6:
                final_selection = random.sample(unique_sample, 6)
                if self._validate(final_selection):
                    return sorted(final_selection), False
        
        return sorted(random.sample(population, 6)), True
    
    # ==================== 算法 6: 間隔/逾期評分 ====================
    def _gap_score(self, number: int) -> int:
        """
        計算號碼的間隔分數（距離上次出現多少期）
        
        Args:
            number: 要計算的號碼
        
        Returns:
            間隔期數（越大表示越久未出現）
        """
        for i, draw in enumerate(self.history):
            if number in draw:
                return i  # 返回距離（0 = 最近一期出現）
        
        return len(self.history)  # 從未出現
    
    def predict_gap_weighted(self, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 6: 結合頻率和間隔的預測
        
        給予「頻繁但最近未出現」的號碼更高權重
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        population = list(range(1, 50))
        
        # 結合頻率和間隔分數
        weights_dict = {}
        for num in population:
            freq = self.frequency.get(num, 1)
            gap = self._gap_score(num)
            
            # 公式: score = frequency * (1 + gap_weight * gap)
            # 頻繁且久未出現的號碼得分最高
            gap_weight = 0.3  # 間隔權重係數
            weights_dict[num] = freq * (1 + gap_weight * gap)
        
        weights = [weights_dict[i] for i in population]
        
        for _ in range(max_attempts):
            sample = random.choices(population, weights=weights, k=10)
            unique_sample = sorted(list(set(sample)))
            
            if len(unique_sample) >= 6:
                final_selection = random.sample(unique_sample, 6)
                if self._validate(final_selection):
                    return sorted(final_selection), False
        
        return sorted(random.sample(population, 6)), True
    
    # ==================== 算法 7: 集成投票（Ensemble）====================
    def predict_ensemble(self, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 7: 集成投票系統（等權重）
        
        運行所有算法，讓每個算法「投票」，選擇得票最高的 6 個號碼
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        # 運行所有算法
        algorithms = [
            'weighted_frequency',
            'recency_weighted',
            'cold_number',
            'smart_hybrid',
            'pair_weighted',
            'gap_weighted'
        ]
        
        # 收集所有預測結果
        vote_counts = defaultdict(int)
        recency_scores = {}  # 用於打破平手
        
        for algo in algorithms:
            try:
                prediction, _ = self.generate_prediction(algorithm=algo)
                for num in prediction:
                    vote_counts[num] += 1
                
                # 記錄時間衰減分數（用於打破平手）
                if algo == 'recency_weighted':
                    for num in prediction:
                        recency_scores[num] = recency_scores.get(num, 0) + 1
            except:
                continue  # 如果某個算法失敗，跳過
        
        # 按得票數排序，平手時使用時間衰減分數
        sorted_candidates = sorted(
            vote_counts.items(),
            key=lambda x: (x[1], recency_scores.get(x[0], 0)),
            reverse=True
        )
        
        # 選擇前 6 個號碼
        if len(sorted_candidates) >= 6:
            ensemble_prediction = sorted([num for num, _ in sorted_candidates[:6]])
            
            # 驗證集成結果
            if self._validate(ensemble_prediction):
                return ensemble_prediction, False
        
        # Fallback: 使用最佳單一算法
        return self.predict_smart_hybrid()
    
    # ==================== 算法 8: 加權集成投票（改進版）====================
    def predict_weighted_ensemble(self, max_attempts: int = 2000, apply_filters: bool = False) -> Tuple[List[int], bool]:
        """
        算法 8: 加權集成投票系統
        
        根據 28 期回測表現分配權重，表現好的算法投票權重更高
        
        權重分配：
        - recency_weighted: 3 (+14.9%)
        - cold_number: 2 (+5.4%)
        - pair_weighted: 2 (+0.6%)
        - smart_hybrid: 1 (-18.6%)
        - gap_weighted: 1 (-9.0%)
        - weighted_frequency: 1 (-18.6%)
        
        可選優化（apply_filters=True）：
        1. 熱勢檢測：最近 10 期出現 3+ 次的號碼作為平手時的決勝因素
        2. 範圍平衡：確保預測涵蓋低(1-16)、中(17-32)、高(33-49)至少 2 個區段
        3. 連號懲罰：減少連續號碼對的出現（如 5,6 或 31,32）
        
        注意：回測顯示這些過濾器會降低準確率，預設關閉
        
        Args:
            apply_filters: 是否套用額外過濾器（預設 False，因回測顯示會降低準確率）
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        votes = {}
        
        for algo, weight in self.ALGO_WEIGHTS.items():
            try:
                prediction, _ = self.generate_prediction(algorithm=algo)
                for num in prediction:
                    votes[num] = votes.get(num, 0) + weight
            except Exception as e:
                continue  # 如果某個算法失敗，跳過
        
        if not votes:
            # 如果所有算法都失敗，使用最佳單一算法
            return self.predict_recency_weighted(max_attempts)
        
        if apply_filters:
            # 使用進階過濾器（實驗性，回測顯示會降低準確率）
            momentum = self._momentum_score(lookback=10)
            
            sorted_candidates = sorted(
                votes.items(),
                key=lambda x: (x[1], momentum.get(x[0], 0)),
                reverse=True
            )
            
            candidates = [num for num, _ in sorted_candidates[:10]]
            
            best_prediction = None
            best_score = -999
            
            for attempt in range(min(100, max_attempts)):
                if len(candidates) >= 6:
                    sample = random.sample(candidates, 6)
                else:
                    sample = candidates + random.sample(range(1, 50), 6 - len(candidates))
                
                sample = sorted(sample)
                
                if not self._validate(sample) or not self._avoid_recent_patterns(sample):
                    continue
                
                vote_score = sum(votes.get(n, 0) for n in sample)
                momentum_bonus = sum(momentum.get(n, 0) for n in sample) * 0.5
                consecutive_penalty = self._consecutive_penalty(sample) * 2
                
                total_score = vote_score + momentum_bonus - consecutive_penalty
                
                if total_score > best_score:
                    best_score = total_score
                    best_prediction = sample
            
            if best_prediction is None:
                best_prediction = sorted([num for num, _ in sorted_candidates[:6]])
            
            score_dict = {num: vote + momentum.get(num, 0) * 0.5 
                         for num, vote in votes.items()}
            best_prediction = self._balance_prediction(best_prediction, score_dict)
        else:
            # 簡單版本：直接選擇得票最高的 6 個號碼（回測證明此版本最佳）
            top_numbers = sorted(votes.items(), key=lambda x: x[1], reverse=True)[:6]
            best_prediction = sorted([num for num, _ in top_numbers])
        
        # 最終驗證
        if self._validate(best_prediction):
            return best_prediction, False
        
        # 驗證失敗，使用最佳單一算法作為 fallback
        return self.predict_recency_weighted(max_attempts)
    
    # ==================== 主要預測接口 ====================
    def generate_prediction(self, algorithm: str = "weighted_ensemble") -> Tuple[List[int], bool]:
        """
        生成預測號碼（主要接口）
        
        Args:
            algorithm: 算法選擇
                - "weighted_frequency": 加權頻率
                - "recency_weighted": 時間衰減加權（改進版，含配對+開獎日加成）
                - "cold_number": 冷號回歸
                - "smart_hybrid": 智能混合
                - "pair_weighted": 配對頻率
                - "gap_weighted": 間隔加權
                - "ensemble": 集成投票（等權重）
                - "weighted_ensemble": 加權集成投票（預設，推薦）
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        algorithms = {
            "weighted_frequency": self.predict_weighted_frequency,
            "recency_weighted": self.predict_recency_weighted,
            "cold_number": self.predict_cold_number_boost,
            "smart_hybrid": self.predict_smart_hybrid,
            "pair_weighted": self.predict_pair_weighted,
            "gap_weighted": self.predict_gap_weighted,
            "ensemble": self.predict_ensemble,
            "weighted_ensemble": self.predict_weighted_ensemble
        }
        
        if algorithm not in algorithms:
            algorithm = "weighted_ensemble"
        
        return algorithms[algorithm]()


# ==================== 便捷函數 ====================
def quick_predict(csv_path: str = None, algorithm: str = "smart_hybrid") -> List[int]:
    """
    快速生成預測（便捷函數）
    
    Args:
        csv_path: CSV 檔案路徑（預設使用當前目錄的 history.csv）
        algorithm: 算法選擇
    
    Returns:
        預測號碼列表
    """
    engine = MarkSixEngine(csv_path=csv_path)
    prediction, _ = engine.generate_prediction(algorithm=algorithm)
    return prediction


def get_hot_numbers(csv_path: str = None, top_n: int = 5) -> List[Tuple[int, int]]:
    """
    取得最熱門號碼（便捷函數）
    
    Args:
        csv_path: CSV 檔案路徑
        top_n: 返回前 N 個
    
    Returns:
        [(號碼, 次數), ...] 列表
    """
    engine = MarkSixEngine(csv_path=csv_path)
    return engine.get_stats(top_n=top_n)


if __name__ == "__main__":
    # 測試預測引擎
    print("🔮 Mark Six 預測引擎測試\n")
    
    engine = MarkSixEngine()
    
    # 測試各種算法
    algorithms = [
        "weighted_frequency", "recency_weighted", "cold_number", 
        "smart_hybrid", "pair_weighted", "gap_weighted", "ensemble"
    ]
    
    for algo in algorithms:
        prediction, used_fallback = engine.generate_prediction(algorithm=algo)
        fallback_text = " (使用 Fallback)" if used_fallback else ""
        emoji = "🏆" if algo == "ensemble" else "📊"
        print(f"{emoji} {algo}: {prediction}{fallback_text}")
    
    # 顯示熱門號碼
    print(f"\n🔥 最熱門的 5 個號碼:")
    for rank, (num, count) in enumerate(engine.get_stats(5), 1):
        print(f"   {rank}. 號碼 {num:2d} - 出現 {count} 次")
