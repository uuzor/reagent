// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Snapshot.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/governance/Governor.sol";

/**
 * @title DeFiYieldToken
 * @dev ERC-20 token with governance, staking, and yield farming capabilities
 */
contract DeFiYieldToken is ERC20, ERC20Burnable, ERC20Permit, ERC20Snapshot, Pausable, Ownable {
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * 10 ** decimals();
    uint256 public constant DEFAULT_ADMIN_ROLE = 0x00;
    
    mapping(address => uint256) public stakedBalances;
    mapping(address => uint256) public rewardsEarned;
    mapping(address => uint256) public lastRewardTime;
    
    uint256 public rewardRate = 100; // tokens per second per staked token
    uint256 public rewardDuration = 7 days;
    uint256 public rewardEndTime;
    
    address public governance;
    
    event Staked(address indexed user, uint256 amount);
    event Unstaked(address indexed user, uint256 amount);
    event RewardsClaimed(address indexed user, uint256 amount);
    event GovernanceUpdated(address indexed oldGovernance, address indexed newGovernance);
    event RewardRateUpdated(uint256 newRate);

    constructor(address _governance) ERC20("DeFiYieldToken", "DFYT") ERC20Permit("DeFiYieldToken") {
        governance = _governance;
        _mint(_governance, 10_000_000 * 10 ** decimals());
    }

    modifier onlyGovernance() {
        require(msg.sender == governance, "Not governance");
        _;
    }

    function pause() external onlyGovernance {
        _pause();
    }

    function unpause() external onlyGovernance {
        _unpause();
    }

    function mint(address to, uint256 amount) external onlyGovernance {
        require(totalSupply() + amount <= MAX_SUPPLY, "Exceeds max supply");
        _mint(to, amount);
    }

    function updateGovernance(address _newGovernance) external onlyGovernance {
        require(_newGovernance != address(0), "Zero address");
        emit GovernanceUpdated(governance, _newGovernance);
        governance = _newGovernance;
    }

    function updateRewardRate(uint256 _newRate) external onlyGovernance {
        rewardRate = _newRate;
        emit RewardRateUpdated(_newRate);
    }

    function setRewardDuration(uint256 _duration) external onlyGovernance {
        rewardDuration = _duration;
    }

    // Staking functions
    function stake(uint256 amount) external whenNotPaused {
        require(amount > 0, "Amount must be > 0");
        _spendAllowance(msg.sender, address(this), amount);
        stakedBalances[msg.sender] += amount;
        lastRewardTime[msg.sender] = block.timestamp;
        emit Staked(msg.sender, amount);
    }

    function unstake(uint256 amount) external whenNotPaused {
        require(amount > 0, "Amount must be > 0");
        require(stakedBalances[msg.sender] >= amount, "Insufficient staked balance");
        stakedBalances[msg.sender] -= amount;
        _transfer(address(this), msg.sender, amount);
        emit Unstaked(msg.sender, amount);
    }

    function claimRewards() external whenNotPaused {
        uint256 pending = calculatePendingRewards(msg.sender);
        require(pending > 0, "No rewards to claim");
        rewardsEarned[msg.sender] = 0;
        lastRewardTime[msg.sender] = block.timestamp;
        _transfer(address(this), msg.sender, pending);
        emit RewardsClaimed(msg.sender, pending);
    }

    function calculatePendingRewards(address user) public view returns (uint256) {
        if (stakedBalances[user] == 0) return 0;
        uint256 timeDiff = block.timestamp - lastRewardTime[user];
        return (stakedBalances[user] * rewardRate * timeDiff) / 1e18;
    }

    function getStakedBalance(address user) external view returns (uint256) {
        return stakedBalances[user];
    }

    function getPendingRewards(address user) external view returns (uint256) {
        return calculatePendingRewards(user);
    }

    // Override ERC20 functions
    function _beforeTokenTransfer(address from, address to, uint256 amount) internal override whenNotPaused {
        super._beforeTokenTransfer(from, to, amount);
    }

    // Receive ETH for rewards funding
    receive() external payable {
        _mint(address(this), msg.value);
    }

    // Governance voting power (uses snapshot balance)
    function getVotes(address account) external view returns (uint256) {
        return balanceOf(account); // Simplified - in production use snapshot mechanism
    }
}