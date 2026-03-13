#!/usr/bin/env python
"""
Mark Six 預測引擎回測工具
測試不同算法的準確度並生成詳細報告
"""

import pandas as pd
import random
import numpy as np
from pathlib import Path
from collections import Counter
from typing import List, Tuple, Dict
import json
from prediction_engine import MarkSixEngine


class BacktestEngine:
    """回測引擎 - 評估預測算法的準確度"""
    
    def __init__(self, csv_path: str = "history.csv", window_size: int = 30):
        """
        初始化回測引擎
        
        Args:
            csv_path: 歷史數據 CSV 路徑
            window_size: 訓練視窗大小（使用最近 N 期預測下一期）
        """
        self.df = pd.read_csv(csv_path)
        self.window_size = window_size
        self.results = {}  # 儲存各算法的結果
        
    def calculate_matches(self, predicted: List[int], actual: List[int]) -> int:
        """
        計算命中數量
        
        Args:
            predicted: 預測號碼
            actual: 實際開獎號碼
        
        Returns:
            命中數量 (0-6)
        """
        return len(set(predicted) & set(actual))
    
    def calculate_confidence_interval(self, matches: List[int], confidence: float = 0.95) -> Tuple[float, float]:
        """
        計算信賴區間
        
        Args:
            matches: 命中數列表
            confidence: 信賴水準（預設 95%）
        
        Returns:
            (下界, 上界)
        """
        if len(matches) < 2:
            return (0, 0)
        
        mean = np.mean(matches)
        std_error = np.std(matches, ddof=1) / np.sqrt(len(matches))
        
        # 使用 t 分佈（小樣本）
        from scipy import stats
        t_value = stats.t.ppf((1 + confidence) / 2, len(matches) - 1)
        margin = t_value * std_error
        
        return (mean - margin, mean + margin)
    
    def run_backtest(self, algorithm: str = "ensemble", start_idx: int = 0, end_idx: int = None) -> Dict:
        """
        執行單一算法的回測
        
        Args:
            algorithm: 算法名稱
            start_idx: 開始索引
            end_idx: 結束索引
        
        Returns:
            回測結果統計
        """
        if end_idx is None:
            end_idx = len(self.df)
        
        if start_idx < self.window_size:
            start_idx = self.window_size
            
        print(f"\n🔍 回測算法: {algorithm}")
        print(f"📊 測試範圍: 第 {start_idx+1} 期 到 第 {end_idx} 期 (共 {end_idx - start_idx} 次預測)")
        
        results = []
        match_distribution = Counter()
        fallback_count = 0
        
        for i in range(start_idx, end_idx):
            # 1. 取得訓練數據
            train_data = self.df.iloc[i-self.window_size:i]
            history_data = train_data[['n1', 'n2', 'n3', 'n4', 'n5', 'n6']].values.tolist()
            
            # 2. 生成預測
            engine = MarkSixEngine(history_data=history_data)
            predicted, used_fallback = engine.generate_prediction(algorithm=algorithm)
            
            # 3. 取得實際結果
            actual_row = self.df.iloc[i]
            actual = [int(actual_row['n1']), int(actual_row['n2']), int(actual_row['n3']), 
                     int(actual_row['n4']), int(actual_row['n5']), int(actual_row['n6'])]
            
            # 4. 計算命中數
            matches = self.calculate_matches(predicted, actual)
            match_distribution[matches] += 1
            
            if used_fallback:
                fallback_count += 1
            
            # 5. 記錄結果
            results.append({
                'draw_index': i + 1,
                'date': actual_row['date'],
                'predicted': predicted,
                'actual': actual,
                'matches': matches,
                'used_fallback': used_fallback
            })
            
            # 顯示進度
            if (i - start_idx + 1) % 20 == 0 or (i - start_idx + 1) == (end_idx - start_idx):
                print(f"   ✓ 已完成 {i - start_idx + 1}/{end_idx - start_idx} 次預測")
        
        # 計算統計數據
        total_predictions = len(results)
        avg_matches = sum(r['matches'] for r in results) / total_predictions
        matches_list = [r['matches'] for r in results]
        
        # 計算信賴區間
        try:
            ci_lower, ci_upper = self.calculate_confidence_interval(matches_list)
        except:
            ci_lower, ci_upper = avg_matches, avg_matches
        
        # 計算統計顯著性
        std_dev = np.std(matches_list, ddof=1) if len(matches_list) > 1 else 0
        
        stats = {
            'algorithm': algorithm,
            'total_predictions': total_predictions,
            'average_matches': avg_matches,
            'confidence_interval_95': (ci_lower, ci_upper),
            'std_deviation': std_dev,
            'match_distribution': dict(match_distribution),
            'fallback_rate': fallback_count / total_predictions * 100,
            'best_predictions': sorted(results, key=lambda x: x['matches'], reverse=True)[:5]
        }
        
        self.results[algorithm] = {'stats': stats, 'details': results}
        return stats
    
    def compare_algorithms(self, algorithms: List[str] = None) -> Dict:
        """
        比較多個算法的表現
        
        Args:
            algorithms: 算法列表（預設測試所有算法）
        
        Returns:
            比較結果
        """
        if algorithms is None:
            algorithms = [
                "weighted_frequency",
                "recency_weighted", 
                "cold_number",
                "smart_hybrid",
                "pair_weighted",
                "gap_weighted",
                "ensemble"
            ]
        
        print("\n" + "="*70)
        print("🏆 算法比較測試（改進版）")
        print("="*70)
        
        comparison = {}
        
        for algo in algorithms:
            stats = self.run_backtest(algorithm=algo)
            comparison[algo] = {
                'avg_matches': stats['average_matches'],
                'ci_95': stats['confidence_interval_95'],
                'std_dev': stats['std_deviation']
            }
        
        return comparison
    
    def compare_with_random(self, num_simulations: int = 100) -> float:
        """
        與純隨機選號比較
        
        Args:
            num_simulations: 模擬次數
        
        Returns:
            純隨機的平均命中數
        """
        print(f"\n🎲 執行 {num_simulations} 次純隨機模擬...")
        
        # 取得任一算法的結果作為基準
        if not self.results:
            return 0.73  # 理論值
        
        first_algo = list(self.results.keys())[0]
        test_results = self.results[first_algo]['details']
        
        random_matches = []
        for _ in range(num_simulations):
            for result in test_results:
                random_pick = sorted(random.sample(range(1, 50), 6))
                matches = self.calculate_matches(random_pick, result['actual'])
                random_matches.append(matches)
        
        avg_random = sum(random_matches) / len(random_matches)
        return avg_random
    
    def print_comparison_report(self, comparison: Dict, random_avg: float = None):
        """
        列印算法比較報告（含信賴區間）
        
        Args:
            comparison: 算法比較結果
            random_avg: 純隨機平均值
        """
        print("\n" + "="*80)
        print("📊 算法表現排名（含 95% 信賴區間）")
        print("="*80)
        
        # 排序算法
        sorted_algos = sorted(comparison.items(), key=lambda x: x[1]['avg_matches'], reverse=True)
        
        print(f"\n{'排名':<6} {'算法':<20} {'平均命中':<15} {'95% CI':<25} {'vs 隨機':<12}")
        print("-" * 80)
        
        for rank, (algo, data) in enumerate(sorted_algos, 1):
            avg_matches = data['avg_matches']
            ci_lower, ci_upper = data['ci_95']
            
            if random_avg:
                improvement = ((avg_matches - random_avg) / random_avg * 100)
                vs_random = f"{improvement:+.1f}%"
            else:
                vs_random = "N/A"
            
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            ci_str = f"[{ci_lower:.3f}, {ci_upper:.3f}]"
            print(f"{medal} {rank:<4} {algo:<20} {avg_matches:.3f}/6        {ci_str:<25} {vs_random}")
        
        if random_avg:
            print(f"\n   📍 純隨機基準: {random_avg:.3f}/6")
        
        # 統計顯著性說明
        print(f"\n   ℹ️  95% 信賴區間: 真實平均值有 95% 機率落在此範圍內")
        print(f"   ⚠️  樣本數越小，信賴區間越寬（不確定性越高）")
        
        print("="*80)
    
    def print_detailed_report(self, algorithm: str):
        """
        列印單一算法的詳細報告
        
        Args:
            algorithm: 算法名稱
        """
        if algorithm not in self.results:
            print(f"❌ 算法 '{algorithm}' 尚未測試")
            return
        
        stats = self.results[algorithm]['stats']
        
        print("\n" + "="*70)
        print(f"📈 詳細報告: {algorithm}")
        print("="*70)
        
        print(f"\n📊 基本統計:")
        print(f"   • 總預測次數: {stats['total_predictions']}")
        print(f"   • 平均命中數: {stats['average_matches']:.3f} / 6")
        print(f"   • 95% 信賴區間: [{stats['confidence_interval_95'][0]:.3f}, {stats['confidence_interval_95'][1]:.3f}]")
        print(f"   • 標準差: {stats['std_deviation']:.3f}")
        print(f"   • Fallback 使用率: {stats['fallback_rate']:.1f}%")
        
        print(f"\n🎯 命中分佈:")
        for matches in range(7):
            count = stats['match_distribution'].get(matches, 0)
            percentage = count / stats['total_predictions'] * 100
            bar = "█" * int(percentage / 2)
            print(f"   {matches}/6 命中: {count:3d} 次 ({percentage:5.1f}%) {bar}")
        
        print(f"\n🏆 最佳預測 (Top 5):")
        for i, pred in enumerate(stats['best_predictions'], 1):
            print(f"   {i}. {pred['date']} - 命中 {pred['matches']}/6")
            print(f"      預測: {pred['predicted']}")
            print(f"      實際: {pred['actual']}")
        
        print("="*70)
    
    def save_results(self, filename: str = "backtest_results.json"):
        """
        儲存回測結果到 JSON
        
        Args:
            filename: 輸出檔案名稱
        """
        output = {}
        
        for algo, data in self.results.items():
            output[algo] = {
                'stats': data['stats'],
                'sample_predictions': data['details'][:10]  # 只儲存前 10 筆範例
            }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 結果已儲存至: {filename}")


def main():
    """主函數 - 執行完整回測"""
    print("🎯 Mark Six 預測引擎回測系統（改進版 - 訓練視窗 30 期）")
    print("="*70)
    
    # 初始化回測引擎（降低訓練視窗從 50 → 30，增加測試樣本）
    backtest = BacktestEngine(
        csv_path="history.csv",
        window_size=30  # 從 50 降至 30，可獲得 28 個測試案例（而非 8 個）
    )
    
    # 比較所有算法
    comparison = backtest.compare_algorithms()
    
    # 與純隨機比較
    random_avg = backtest.compare_with_random(num_simulations=100)
    
    # 列印比較報告
    backtest.print_comparison_report(comparison, random_avg)
    
    # 列印最佳算法的詳細報告
    best_algo = max(comparison.items(), key=lambda x: x[1]['avg_matches'])[0]
    backtest.print_detailed_report(best_algo)
    
    # 儲存結果
    backtest.save_results()
    
    print("\n✅ 回測完成！")


if __name__ == "__main__":
    main()
