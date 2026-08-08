function PD=Center_2(PD, shift)
%function PD=Center_2(PD, shift)
% add shift
for i=1:6,
       PD(:,i)=PD(:,i)+shift(i);  
end
