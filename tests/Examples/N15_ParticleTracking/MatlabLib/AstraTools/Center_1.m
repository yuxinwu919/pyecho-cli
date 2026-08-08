function [PD,shift]=Center_1(PD, flags)
%function [PD,shift]PD=Center_1(PD, flags)
% substract mean values
for i=1:6,
   if flags(i)
       shift(i)=mean(PD(:,i));
       PD(:,i)=PD(:,i)-shift(i);
   else
       shift(i)=0;
   end
end;
