"use client";

import { CapabilityCard } from "@/lib/types";
import CapabilityCardComponent from "@/components/common/CapabilityCard";

const CARDS: CapabilityCard[] = [
  {
    icon: "📊",
    title: "供应商分析",
    description: "查询供应商信息，结合已获取的数据给出分析",
    prompt: "查询前 20 家供应商，并说明查询范围",
  },
  {
    icon: "🛒",
    title: "采购订单查询",
    description: "只读查询采购订单状态，不创建或修改单据",
    prompt: "查询最近可访问的采购订单及其状态",
  },
  {
    icon: "📦",
    title: "库存查询",
    description: "按已配置的公司和仓库范围查询库存",
    prompt: "查看当前库存查询信息",
  },
  {
    icon: "🔍",
    title: "物料查询",
    description: "查询物料编码、名称、分类和库存单位",
    prompt: "查询前 20 条物料信息",
  },
];

interface Props {
  onPromptClick: (prompt: string) => void;
}

export default function WelcomeScreen({ onPromptClick }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-8">
      <div className="max-w-2xl w-full text-center">
        {/* 标题 */}
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          ERPNext 供应链协同助手
        </h1>
        <p className="text-sm text-gray-500 mb-8">
          阶段一 · 只读查询供应商、物料、仓库、库存与采购订单
        </p>

        {/* 功能卡片 2x2 */}
        <div className="grid grid-cols-2 gap-4">
          {CARDS.map((card) => (
            <CapabilityCardComponent
              key={card.title}
              card={card}
              onClick={onPromptClick}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
