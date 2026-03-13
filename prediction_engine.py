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
    
    def __init__(self, history_data: List[List[int]] = None, csv_path: str = None):
        """
        初始化預測引擎
        
        Args:
            history_data: 歷史開獎數據列表 [[n1, n2, n3, n4, n5, n6], ...]
            csv_path: CSV 檔案路徑（如果未提供 history_data）
        """
        if history_data is not None:
            self.history = history_data
        elif csv_path:
            self.history = self._load_from_csv(csv_path)
        else:
            # 預設載入當前目錄的 history.csv
            default_path = Path(__file__).parent / "history.csv"
            self.history = self._load_from_csv(str(default_path))
        
        # 展平所有號碼以計算頻率
        self.flat_list = [num for draw in self.history for num in draw]
        self.frequency = Counter(self.flat_list)
    
    def _load_from_csv(self, csv_path: str, window_size: int = 30) -> List[List[int]]:
        """
        從 CSV 載入歷史數據
        
        Args:
            csv_path: CSV 檔案路徑
            window_size: 載入最近 N 期數據
        
        Returns:
            歷史數據列表
        """
        df = pd.read_csv(csv_path)
        # 只取最近 window_size 期的 6 個主要號碼（不含 special_number）
        history_data = df[['n1', 'n2', 'n3', 'n4', 'n5', 'n6']].head(window_size).values.tolist()
        return history_data
    
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
    
    # ==================== 算法 2: 時間衰減加權 ====================
    def predict_recency_weighted(self, decay_factor: float = 0.95, max_attempts: int = 2000) -> Tuple[List[int], bool]:
        """
        算法 2: 時間衰減加權
        
        最近的開獎結果權重更高，隨時間遞減
        
        Args:
            decay_factor: 衰減係數 (0.9=快速衰減, 0.99=慢速衰減)
        
        Returns:
            (預測號碼列表, 是否使用 fallback)
        """
        weights_dict = {}
        
        # 從最舊到最新，權重遞增
        for draw_idx, draw in enumerate(self.history):
            weight = decay_factor ** (len(self.history) - draw_idx - 1)
            for num in draw:
                weights_dict[num] = weights_dict.get(num, 0) + weight
        
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
        算法 7: 集成投票系統
        
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
    
    # ==================== 主要預測接口 ====================
    def generate_prediction(self, algorithm: str = "ensemble") -> Tuple[List[int], bool]:
        """
        生成預測號碼（主要接口）
        
        Args:
            algorithm: 算法選擇
                - "weighted_frequency": 加權頻率
                - "recency_weighted": 時間衰減加權
                - "cold_number": 冷號回歸
                - "smart_hybrid": 智能混合
                - "pair_weighted": 配對頻率
                - "gap_weighted": 間隔加權
                - "ensemble": 集成投票（預設，推薦）
        
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
            "ensemble": self.predict_ensemble
        }
        
        if algorithm not in algorithms:
            algorithm = "ensemble"
        
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
